import json
from pathlib import Path
from fastapi.testclient import TestClient

from case3.api import app
from case3 import run_store


def test_history_sync_survives_windows_replace_lock(tmp_path: Path, monkeypatch) -> None:
    """WinError 32: Path.replace cannot overwrite a locked user_history.json.

    The desk log showed this as POST /api/history/sync 500. Save must fall
    back to an in-place write and keep the pin.
    """
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    (tmp_path / "runs" / "out").mkdir(parents=True, exist_ok=True)
    real_replace = Path.replace

    def locked_replace(self: Path, target: Path):
        if self.name == "user_history.tmp" and target.name == "user_history.json":
            raise PermissionError(32, "file is locked", str(target))
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", locked_replace)
    client = TestClient(app)
    res = client.post(
        "/api/history/sync",
        json={
            "items": [{"runId": "run_20261110T120000Z", "pinned": True}],
            "folders": [],
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    saved = json.loads((tmp_path / "runs" / "user_history.json").read_text(encoding="utf-8"))
    assert saved["pinned"] == ["run_20261110T120000Z"]


def test_api_history_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    (tmp_path / "runs" / "out").mkdir(parents=True, exist_ok=True)
    client = TestClient(app)

    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["folders"] == []


def test_api_history_scan_and_sync(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    out_dir = tmp_path / "runs" / "out"
    run1 = out_dir / "run_20261107T120000Z"
    run1.mkdir(parents=True, exist_ok=True)
    (run1 / "meta.json").write_text(
        json.dumps(
            {
                "run_id": "run_20261107T120000Z",
                "started_at": "20261107T120000Z",
                "status": "ok",
                "preview": {"title": "Финансовый отчёт Q3"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    client = TestClient(app)

    # 1. Get history: should pick up run1
    res = client.get("/api/history")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["runId"] == "run_20261107T120000Z"
    assert items[0]["title"] == "Финансовый отчёт Q3"
    assert items[0]["pinned"] is False

    # 2. Sync history: pin run1 and add a folder
    sync_payload = {
        "items": [
            {
                "runId": "run_20261107T120000Z",
                "pinned": True,
                "folderId": "fld_1",
            }
        ],
        "folders": [{"id": "fld_1", "name": "Финансы", "createdAt": 1731000000000}],
    }
    res_sync = client.post("/api/history/sync", json=sync_payload)
    assert res_sync.status_code == 200
    assert res_sync.json()["ok"] is True

    # 3. Get history again: should reflect pinned status and folder
    res2 = client.get("/api/history")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["folders"]) == 1
    assert data2["folders"][0]["name"] == "Финансы"
    assert len(data2["items"]) == 1
    assert data2["items"][0]["pinned"] is True
    assert data2["items"][0]["folderId"] == "fld_1"

    # 4. Sync history: delete all folders (folders=[])
    res_delete = client.post("/api/history/sync", json={"items": [], "folders": []})
    assert res_delete.status_code == 200

    # 5. Get history again: should have empty folders and folderId cleared
    res3 = client.get("/api/history")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["folders"] == []
    assert len(data3["items"]) == 1
    assert data3["items"][0]["pinned"] is True
    assert data3["items"][0]["folderId"] is None


def test_history_lists_24_unpinned_plus_older_pin(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    out_dir = tmp_path / "runs" / "out"
    out_dir.mkdir(parents=True)
    for i in range(30):
        run_id = f"run_20261107T12{i:04d}Z"
        run_dir = out_dir / run_id
        run_dir.mkdir()
        (run_dir / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "started_at": f"20261107T12{i:04d}Z",
                    "status": "ok",
                    "preview": {"title": f"Отчёт {i}"},
                }
            ),
            encoding="utf-8",
        )
    client = TestClient(app)
    first = client.get("/api/history")
    assert first.status_code == 200
    items = first.json()["items"]
    assert len(items) == 24
    assert items[0]["title"] == "Отчёт 29"

    oldest = "run_20261107T120000Z"
    synced = client.post(
        "/api/history/sync",
        json={"items": [{"runId": oldest, "pinned": True}], "folders": []},
    )
    assert synced.status_code == 200
    second = client.get("/api/history")
    ids = [it["runId"] for it in second.json()["items"]]
    assert oldest in ids
    assert len(ids) == 25
    assert second.json()["items"][0]["runId"] == oldest


def test_history_index_skips_unchanged_meta(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    out_dir = tmp_path / "runs" / "out"
    run_dir = out_dir / "run_20261107T120000Z"
    run_dir.mkdir(parents=True)
    meta_path = run_dir / "meta.json"
    meta_path.write_text(
        json.dumps({"run_id": "run_20261107T120000Z", "status": "ok", "title": "A"}),
        encoding="utf-8",
    )
    reads: list[str] = []
    real_read = Path.read_text

    def _counting_read(self: Path, *args, **kwargs):  # noqa: ANN001
        if self.name == "meta.json":
            reads.append(str(self))
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _counting_read)
    client = TestClient(app)
    assert client.get("/api/history").status_code == 200
    assert len(reads) == 1
    reads.clear()
    assert client.get("/api/history").status_code == 200
    assert reads == []


def test_history_shows_one_row_per_chat(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    out = tmp_path / "runs" / "out"
    first = "source_20261118T100000Z"
    second = "source_20261118T110000Z"
    for run_id, prior, title in (
        (first, "", "Отчёт"),
        (second, first, "Ещё точнее"),
    ):
        folder = out / run_id
        folder.mkdir(parents=True)
        (folder / "meta.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "prior_run_id": prior,
                    "status": "ok",
                    "preview": {"title": title},
                    "started_at": run_id.removeprefix("source_"),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    client = TestClient(app)
    items = client.get("/api/history").json()["items"]
    assert [item["runId"] for item in items] == [second]
