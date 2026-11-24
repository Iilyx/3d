"""Slides job API: 409 when report not ok; 202 + offline when ok."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(api_client: TestClient) -> TestClient:
    return api_client


def _seed_ok_run(
    tmp_path: Path, run_id: str, *, source: str = "Выручка 120 млн. Доля 35%."
) -> Path:
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    src = tmp_path / "runs" / "uploads" / run_id / "source.txt"
    src.parent.mkdir(parents=True)
    src.write_text(source, encoding="utf-8")
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "ok",
                "stage": "ok",
                "source": str(src),
                "intent": "- палитра графиков: Atelier (atelier)",
                "charts_planned": [],
                "figures_planned": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "report.pdf").write_bytes(b"%PDF-1.4 fake")
    return out


def test_slides_crash_writes_error(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "run_slides_crash"
    _seed_ok_run(tmp_path, run_id)

    def _boom(rid: str, **_kw: object) -> None:
        raise RuntimeError("simulated slides crash")

    monkeypatch.setattr("case3.slides_job.run_slides_job", _boom)

    r = client.post(f"/api/runs/{run_id}/slides")
    assert r.status_code == 202, r.text

    import time

    body: dict = {}
    for _ in range(80):
        st = client.get(f"/api/runs/{run_id}/status")
        body = st.json()
        if body.get("slides_status") == "error":
            break
        time.sleep(0.05)
    assert body.get("slides_status") == "error"
    assert "simulated slides crash" in (body.get("slides_error") or "")


def test_slides_409_when_not_ok(client: TestClient, tmp_path: Path) -> None:
    run_id = "run_bad"
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps({"run_id": run_id, "status": "running", "stage": "llm"}),
        encoding="utf-8",
    )
    r = client.post(f"/api/runs/{run_id}/slides")
    assert r.status_code == 409


def test_slides_202_and_offline_job(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "run_slides_ok"
    _seed_ok_run(tmp_path, run_id)

    def _fake_pngs(deck, *, work_root, out_dir, chart_png_by_id=None, media_png_by_id=None, **_kw):
        from PIL import Image

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i, _slide in enumerate(deck.get("slides") or [], start=1):
            p = out_dir / f"slide_{i:02d}.png"
            Image.new("RGB", (64, 36), (40, 80, 40)).save(p)
            paths.append(p)
        return paths

    monkeypatch.setattr("case3.slides_job.render_deck_pngs", _fake_pngs)

    def _fake_deck_pdf(pptx_path, pngs, dest_pdf):
        """Skip LibreOffice — stitch is enough for API contract tests."""
        dest = Path(dest_pdf)
        dest.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\ntrailer\n%%EOF\n")
        return dest, "png_stitch"

    monkeypatch.setattr("case3.slides_job.write_deck_pdf", _fake_deck_pdf)

    def _fake_job(rid: str) -> None:
        from case3.slides_job import run_slides_job

        run_slides_job(
            rid,
            root=tmp_path,
            skip_llm_ir={
                "version": 1,
                "aspect": "16:9",
                "palette": "atelier",
                "language": "ru",
                "slides": [
                    {
                        "id": "s01",
                        "layout": "title",
                        "title": "Итоги",
                        "subtitle": "Кратко",
                    },
                    {
                        "id": "s02",
                        "layout": "kpi_row",
                        "title": "Цифры",
                        "kpis": [
                            {"label": "Выручка", "value": "120 млн"},
                            {"label": "Доля", "value": "35%"},
                        ],
                    },
                    {
                        "id": "s03",
                        "layout": "bullets",
                        "title": "Факты",
                        "bullets": ["Выручка 120 млн"],
                    },
                    {
                        "id": "s04",
                        "layout": "closing",
                        "title": "Далее",
                        "bullets": ["Шаг"],
                    },
                ],
            },
        )

    import case3.api_slides as slides_mod

    monkeypatch.setattr(slides_mod, "_bg_run_slides", _fake_job)

    r = client.post(f"/api/runs/{run_id}/slides")
    assert r.status_code == 202, r.text
    assert r.json()["slides_status"] == "running"
    assert r.json()["slides_stage"] == "starting"

    # Daemon thread — poll until job finishes (TestClient no longer awaits BackgroundTasks).
    import time

    body: dict = {}
    for _ in range(200):
        st = client.get(f"/api/runs/{run_id}/status")
        assert st.status_code == 200
        body = st.json()
        if body.get("slides_status") in {"ok", "error"}:
            break
        time.sleep(0.05)
    assert body.get("slides_status") == "ok", body.get("slides_error") or body
    assert "pptx" in (body.get("downloads") or {})
    assert "deck_pdf" in (body.get("downloads") or {})
    assert "pdf" in (body.get("downloads") or {})
    assert body["downloads"]["pdf"].endswith("report.pdf")

    g = client.get(f"/api/runs/{run_id}/slides")
    assert g.status_code == 200
    assert g.json()["deck"]["slides"][0]["layout"] == "title"
    assert len(g.json()["slide_pngs"]) == 4


def test_slides_ir_patch_coalesces_no_409(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent PATCHes queue — never 409 while a patch rebuild is running."""
    run_id = "run_patch_q"
    out = _seed_ok_run(tmp_path, run_id)
    slides = out / "slides"
    slides.mkdir(parents=True)
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "ru",
        "slides": [
            {
                "id": "s01",
                "layout": "title",
                "title": "A",
                "subtitle": "x",
            }
        ],
    }
    (slides / "deck.json").write_text(
        json.dumps(deck, ensure_ascii=False), encoding="utf-8"
    )
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["slides_status"] = "ok"
    meta["slides_artifacts"] = {"pptx": "x.pptx", "deck_pdf": "x.pdf", "png_count": 1}
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    gate = {"n": 0}
    import threading

    hold = threading.Event()

    def _slow_rebuild(rid: str, patched: dict, **_kw: object) -> dict:
        gate["n"] += 1
        hold.wait(timeout=2.0)
        meta_path = out / "meta.json"
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        m["slides_status"] = "ok"
        m["slides_stage"] = "ok"
        meta_path.write_text(json.dumps(m), encoding="utf-8")
        (slides / "deck.json").write_text(
            json.dumps(patched, ensure_ascii=False), encoding="utf-8"
        )
        return m

    monkeypatch.setattr(
        "case3.slides_job.rebuild_slides_from_deck", _slow_rebuild
    )

    r1 = client.patch(
        f"/api/runs/{run_id}/slides/ir",
        json={"slides": [{"id": "s01", "title": "One"}]},
    )
    assert r1.status_code == 202, r1.text
    r2 = client.patch(
        f"/api/runs/{run_id}/slides/ir",
        json={"slides": [{"id": "s01", "title": "Two"}]},
    )
    assert r2.status_code == 202, r2.text
    assert r2.json().get("queued") is True
    hold.set()
    import time

    for _ in range(40):
        st = client.get(f"/api/runs/{run_id}/status")
        if st.json().get("slides_status") == "ok":
            break
        time.sleep(0.05)
    assert gate["n"] >= 1
    final = json.loads((slides / "deck.json").read_text(encoding="utf-8"))
    assert final["slides"][0]["title"] == "Two"


def test_downloads_do_not_collide_deck_pdf(client: TestClient, tmp_path: Path) -> None:
    run_id = "run_collide"
    out = _seed_ok_run(tmp_path, run_id)
    (out / "report_deck.pdf").write_bytes(b"%PDF deck")
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["slides_status"] = "ok"
    meta["slides_artifacts"] = {
        "pptx": "report_slides.pptx",
        "deck_pdf": "report_deck.pdf",
    }
    (out / "report_slides.pptx").write_bytes(b"PK fake")
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    st = client.get(f"/api/runs/{run_id}/status")
    d = st.json()["downloads"]
    assert d["pdf"].endswith("report.pdf")
    assert d["deck_pdf"].endswith("report_deck.pdf")
    assert d["pptx"].endswith("report_slides.pptx")


def test_status_includes_slide_pngs_when_twins_exist(
    client: TestClient, tmp_path: Path
) -> None:
    """Liber chat/rail hydrate from /status — pptx alone left preview empty."""
    run_id = "run_status_pngs"
    out = _seed_ok_run(tmp_path, run_id)
    slides = out / "slides"
    slides.mkdir(parents=True, exist_ok=True)
    (slides / "slide_01.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (slides / "slide_02.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["slides_status"] = "ok"
    meta["slides_artifacts"] = {
        "pptx": "report_slides.pptx",
        "deck_pdf": "report_deck.pdf",
        "png_count": 2,
    }
    (out / "report_slides.pptx").write_bytes(b"PK fake")
    (out / "report_deck.pdf").write_bytes(b"%PDF")
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    st = client.get(f"/api/runs/{run_id}/status")
    assert st.status_code == 200
    body = st.json()
    pngs = body.get("slide_pngs") or []
    assert len(pngs) == 2
    assert pngs[0].endswith("/slides/png/slide_01.png")
    assert pngs[1].endswith("/slides/png/slide_02.png")


def test_auto_kick_keeps_cancel_and_does_not_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from case3.api_slides import try_claim_slides_start

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "run_cancel_before_slides"
    out = _seed_ok_run(tmp_path, run_id)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["cancel_requested"] = True
    meta["slides_status"] = "idle"
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    logs = tmp_path / "runs" / "logs" / run_id
    logs.mkdir(parents=True)

    claimed, _ = try_claim_slides_start(
        run_id,
        out_dir=out,
        logs_dir=logs,
        kick_source="api_auto",
        only_if_unbuilt=True,
    )
    assert claimed is False
    disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk["cancel_requested"] is True
    assert disk.get("slides_status") != "running"


def test_post_slides_api_auto_keeps_cancel(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chat auto-kick after Stop must not clear cancel or start the deck."""
    run_id = "run_auto_kick_http_cancel"
    out = _seed_ok_run(tmp_path, run_id)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["cancel_requested"] = True
    meta["slides_status"] = "idle"
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    started: list[str] = []
    monkeypatch.setattr(
        "case3.api_slides._kick_slides_thread", lambda rid: started.append(rid)
    )

    r = client.post(
        f"/api/runs/{run_id}/slides",
        json={"theme_pack": "atelier", "kick_source": "api_auto"},
    )
    assert r.status_code == 202, r.text
    disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk["cancel_requested"] is True
    assert disk.get("slides_status") != "running"
    assert started == []


def test_manual_slides_start_clears_stale_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from case3.api_slides import try_claim_slides_start

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "run_slides_after_stop"
    out = _seed_ok_run(tmp_path, run_id)
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["cancel_requested"] = True
    meta["slides_status"] = "idle"
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    logs = tmp_path / "runs" / "logs" / run_id
    logs.mkdir(parents=True)

    claimed, _ = try_claim_slides_start(
        run_id,
        out_dir=out,
        logs_dir=logs,
    )
    assert claimed is True
    disk = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk.get("cancel_requested") is not True
    assert disk["slides_status"] == "running"


def test_slides_patch_mark_keeps_cancel() -> None:
    from case3.api_slides import note_slides_patch

    meta = {"run_id": "r", "status": "ok", "cancel_requested": True}
    note_slides_patch(meta, "r")
    assert meta["cancel_requested"] is True
    assert meta["slides_status"] == "running"
    assert meta["slides_stage"] == "patch"


def test_try_claim_slides_start_is_single_winner_under_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading
    from case3.api_slides import try_claim_slides_start

    monkeypatch.setattr("case3.run_store.ROOT", tmp_path)
    run_id = "run_race_claim"
    out = _seed_ok_run(tmp_path, run_id)
    logs = tmp_path / "runs" / "logs" / run_id
    barrier = threading.Barrier(2)
    results: list[bool] = []

    def worker() -> None:
        barrier.wait()
        claimed, _ = try_claim_slides_start(
            run_id,
            out_dir=out,
            logs_dir=logs,
            theme_pack="atelier",
            structure_id=None,
            style_settings=None,
        )
        results.append(claimed)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert sorted(results) == [False, True]


def test_download_slide_media_prefers_newer_figure(client: TestClient, tmp_path: Path) -> None:
    import os
    import time
    run_id = "run_media_stale"
    out = _seed_ok_run(tmp_path, run_id)
    charts_dir = out / "slides" / "charts"
    charts_dir.mkdir(parents=True)
    old_png = charts_dir / "cht_01.png"
    old_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"OLD")
    os.utime(old_png, (time.time() - 100, time.time() - 100))

    figs_dir = out / "figures"
    figs_dir.mkdir(parents=True)
    new_png = figs_dir / "cht_01.png"
    new_png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"NEW_EDITED")
    os.utime(new_png, (time.time(), time.time()))

    resp = client.get(f"/api/runs/{run_id}/slides/media/cht_01.png")
    assert resp.status_code == 200
    assert resp.content == b"\x89PNG\r\n\x1a\n" + b"NEW_EDITED"


def test_structure_rebuild_0_writes_ir_without_worker(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Add/duplicate stays in deck.json. Twin/PPTX wait for Готово."""
    run_id = "run_struct0"
    out = _seed_ok_run(tmp_path, run_id)
    slides = out / "slides"
    slides.mkdir(parents=True)
    deck = {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "language": "ru",
        "slides": [
            {"id": "s01", "layout": "title", "title": "A"},
            {"id": "s02", "layout": "bullets", "title": "B", "bullets": ["x"]},
        ],
    }
    (slides / "deck.json").write_text(
        json.dumps(deck, ensure_ascii=False), encoding="utf-8"
    )
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    meta["slides_status"] = "ok"
    (out / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    def _boom(*_a: object, **_k: object) -> dict:
        raise AssertionError("structure rebuild=0 must not start the slides worker")

    monkeypatch.setattr("case3.slides_job.rebuild_slides_from_deck", _boom)

    r = client.post(
        f"/api/runs/{run_id}/slides/structure?rebuild=0",
        json={"op": "duplicate", "id": "s02"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("rebuilt") is False
    assert body.get("slides_status") == "ok"
    ids = [s["id"] for s in body["deck"]["slides"]]
    assert ids[:2] == ["s01", "s02"]
    assert len(ids) == 3
    target = str((body.get("undo") or {}).get("target") or "")
    assert target.split(",")[0] == ids[2]
    assert "s02" in target.split(",")
    assert "duplicate" not in target.split(",")
    disk = json.loads((slides / "deck.json").read_text(encoding="utf-8"))
    assert [s["id"] for s in disk["slides"]] == ids
    disk_meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert disk_meta.get("slides_status") != "running"


