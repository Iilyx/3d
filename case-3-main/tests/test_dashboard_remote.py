"""Colleague /shot JSON → file bytes. Paths on his disk are not enough."""

from __future__ import annotations

import base64

import pytest

from case3.dashboard_remote import (
    DashboardRemoteError,
    capture_documents,
    files_from_shot,
    fetch_dashboard_preview,
    fetch_dashboards,
    fetch_filter_catalog,
    open_named_dashboard,
    filters_from_model,
    finish_dashboard_phrase,
    might_ask_dashboard,
    open_payload,
    plan_dashboard_phrase,
    read_filter_catalog,
    service_base,
    viewer_url,
)


def test_service_base_and_viewer_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_SERVICE_URL", "http://10.0.0.8:8040/")
    assert service_base() == "http://10.0.0.8:8040"
    assert viewer_url() == "http://10.0.0.8:8040/viewer"


def test_files_from_shot_prefers_inline_bytes() -> None:
    raw = b"\x89PNG\r\nhello"
    pdf = b"%PDF-1.4 table"
    payload = {
        "ok": True,
        "png": {
            "name": "dashboard_20261122.png",
            "data_b64": base64.b64encode(raw).decode(),
            "path": "/remote/nope.png",
        },
        "pdfs": [
            {
                "name": "Оплаты_20261122.pdf",
                "data_b64": base64.b64encode(pdf).decode(),
            }
        ],
    }
    files = files_from_shot(payload, fetch_named=lambda _name: None)
    assert [(item.name, item.ext, item.data) for item in files] == [
        ("dashboard_20261122.png", "png", raw),
        ("Оплаты_20261122.pdf", "pdf", pdf),
    ]


def test_files_from_shot_reads_his_path_on_this_machine(tmp_path) -> None:
    png = tmp_path / "screen.png"
    png.write_bytes(b"\x89PNG-local")
    payload = {
        "ok": True,
        "png": {"name": "screen.png", "path": str(png), "kind": "png"},
    }
    called = False

    def fetch_named(_name: str) -> bytes | None:
        nonlocal called
        called = True
        return None

    files = files_from_shot(payload, fetch_named=fetch_named)
    assert called is False
    assert files[0].data == b"\x89PNG-local"


def test_files_from_shot_downloads_when_the_body_is_only_a_path() -> None:
    payload = {
        "ok": True,
        "png": {"name": "screen.png", "path": r"D:\exports\screen.png"},
        "pdfs": [{"name": "Table.pdf", "path": r"D:\exports\Table.pdf"}],
    }
    fetched: list[str] = []

    def fetch_named(name: str) -> bytes | None:
        fetched.append(name)
        return b"bytes:" + name.encode()

    files = files_from_shot(payload, fetch_named=fetch_named)
    assert fetched == ["screen.png", "Table.pdf"]
    assert files[0].data == b"bytes:screen.png"
    assert files[1].ext == "pdf"


def test_capture_documents_uses_one_parse_for_png_and_pdf() -> None:
    png = b"\x89PNG\r\nhello"
    pdf = b"%PDF-1.4 table"
    payload = {
        "ok": True,
        "png": {"name": "dashboard_20261122.png", "data_b64": base64.b64encode(png).decode()},
        "pdfs": [{"name": "Оплаты.pdf", "data_b64": base64.b64encode(pdf).decode()}],
    }
    seen: list[tuple[bytes | None, bytes | None]] = []

    class Parsed:
        markdown = "# Данные дашборда\n\n## Экран\n\nкарточка\n\n## Таблица PDF\n\n| a |\n"
        warnings = ["тонкая линия"]

    def parse(*, png=None, pdf=None):
        seen.append((png, pdf))
        return Parsed()

    docs = capture_documents(payload, fetch_named=lambda _name: None, parse=parse)
    assert seen == [(png, pdf)]
    assert len(docs) == 1
    assert docs[0]["name"] == "dashboard_20261122.png"
    assert docs[0]["markdown"].startswith("# Данные дашборда")
    assert "Таблица PDF" in docs[0]["markdown"]


def test_capture_documents_names_the_screen_from_its_heading() -> None:
    png = b"\x89PNG\r\nhello"
    payload = {
        "ok": True,
        "png": {"name": "dashboard_20261122_100249.png", "data_b64": base64.b64encode(png).decode()},
    }

    class Parsed:
        markdown = (
            "# Данные дашборда\n\n## Экран\n\n## Заголовок\n"
            "Поступления за январь 2025 года (с нарастающим итогом)\n"
        )
        warnings: list[str] = []

    docs = capture_documents(payload, fetch_named=lambda _name: None, parse=lambda **_k: Parsed())
    assert docs[0]["name"] == "Поступления за январь 2025 года"


_CATALOG = {
    "filters": [
        {
            "name": "Month",
            "alias": "Месяц",
            "choices": [
                {"key": "2", "value": "Февраль"},
                {"key": "3", "value": "Март"},
            ],
        },
        {
            "name": "Year",
            "alias": "Год",
            "choices": [
                {"key": "2024", "value": "2024"},
                {"key": "2025", "value": "2025"},
            ],
        },
        {"name": "Region", "alias": "Регион", "choices": [{"key": "7", "value": "Минск"}]},
    ]
}


_OPEN_CATALOG = {
    "mrt": "last.mrt",
    "filters": [
        {
            "name": "trendtype",
            "choices": [
                {"key": "cumulative", "value": "накопительный"},
                {"key": "period", "value": "за период"},
            ],
        },
        {
            "name": "typenum",
            "choices": [
                {"key": "1", "value": "тыс."},
                {"key": "1000000", "value": "млн."},
            ],
        },
        {
            "name": "month",
            "choices": [{"key": "2", "value": "Февраль"}],
        },
        {
            "name": "year",
            "choices": [{"key": "2025", "value": "2025"}],
        },
        {
            "name": "vtypevd",
            "choices": [{"key": "0000000", "value": "все"}],
        },
    ],
}


def test_phrase_keeps_february_25_and_drops_an_unnamed_filter() -> None:
    phrase = "хочу данные по февраль 25"
    raw = '{"pull": true, "filters": {"Месяц": "Февраль", "Year": "2025", "Region": "Минск"}}'
    picked = filters_from_model(_CATALOG, phrase, raw)
    assert picked == {"Month": 2, "Year": 2025}
    assert might_ask_dashboard(phrase) is True
    assert might_ask_dashboard("сделай короче") is False
    assert might_ask_dashboard("куплю смартфон") is False


def test_model_refusal_stays_a_normal_message() -> None:
    def complete(**_kwargs: object) -> str:
        return '{"pull": false, "filters": {}}'

    plan = plan_dashboard_phrase("хочу данные по февраль 25", _CATALOG, complete)
    assert plan == {"pull": False}
    # Even when catalog has default values (_LIVE_CATALOG), if the user asks a normal report/presentation
    # request mentioning a month ("Сделай презентацию про итоги за январь: выручка 100") and model says pull=false,
    # it MUST NOT hijack the message into a dashboard card!
    plan_live = plan_dashboard_phrase(
        "Сделай презентацию про продажи за февраль: выручка 100 млн",
        _LIVE_CATALOG,
        complete,
    )
    assert plan_live == {"pull": False}


def test_plan_skips_the_model_when_the_sentence_is_not_about_data() -> None:
    called = False

    def complete(**_kwargs):
        nonlocal called
        called = True
        return "{}"

    assert plan_dashboard_phrase("сделай короче", _CATALOG, complete) == {"pull": False}
    assert called is False


def test_plan_asks_again_when_the_first_answer_has_no_sentence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_SERVICE_URL", "http://127.0.0.1:8040")
    seen: list[str] = []

    def complete(**kwargs: object) -> str:
        seen.append(str(kwargs.get("system") or ""))
        if len(seen) == 1:
            return '{"pull": true, "filters": {"Month": "Февраль"}}'
        return "Открываю февраль, на экране будет прошлый месяц."

    plan = plan_dashboard_phrase("хочу данные по февраль 25", _CATALOG, complete)
    assert len(seen) == 2
    assert plan["reply"] == "Открываю февраль, на экране будет прошлый месяц."


def test_plan_opens_when_the_model_maps_the_phrase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_SERVICE_URL", "http://127.0.0.1:8040")

    def complete(**_kwargs: object) -> str:
        return (
            '{"pull": true, "filters": {"Month": "Февраль", "Year": "2025"}, '
            '"say": "Открываю февраль 2025."}'
        )

    plan = plan_dashboard_phrase("хочу данные по февраль 25", _CATALOG, complete)
    assert plan["pull"] is True
    assert plan["filters"] == {"Month": 2, "Year": 2025}
    assert plan["reply"] == "Открываю февраль 2025."
    assert plan["viewer"].endswith("/open")


def test_open_payload_uses_choice_keys() -> None:
    phrase = "накопительный итог, тыс., февраль 2025, все виды"
    raw = (
        '{"pull": true, "filters": {'
        '"trendtype": "накопительный", "typenum": "тыс.", '
        '"month": "Февраль", "year": "2025", "vtypevd": "все"}}'
    )
    picked = filters_from_model(_OPEN_CATALOG, phrase, raw)
    assert picked == {
        "trendtype": "cumulative",
        "typenum": 1,
        "month": 2,
        "year": 2025,
        "vtypevd": "0000000",
    }
    assert open_payload(picked) == {"filters": picked}


_LIVE_CATALOG = {
    "mrt": "last.mrt",
    "filters": [
        {
            "name": "trendtype",
            "alias": "Тип тренда",
            "value": "cumulative",
            "choices": [
                {"key": "cumulative", "value": "накопительный"},
                {"key": "nocumulative", "value": "за период"},
            ],
        },
        {
            "name": "typenum",
            "alias": "Единицы",
            "value": 1,
            "choices": [
                {"key": "1", "value": "тыс."},
                {"key": "1000000", "value": "млн."},
            ],
        },
        {
            "name": "month",
            "alias": "Месяц",
            "value": "2",
            "choices": [
                {"key": "2", "value": "Февраль"},
                {"key": "3", "value": "Март"},
            ],
        },
        {
            "name": "year",
            "alias": "Год",
            "value": "2025",
            "choices": [{"key": "2025", "value": "2025"}],
        },
        {
            "name": "vtypevd",
            "alias": "Вид",
            "value": "0000000",
            "choices": [{"key": "0000000", "value": "все"}],
        },
    ],
}


def test_open_dashboard_posts_catalog_values_without_a_named_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_SERVICE_URL", "http://127.0.0.1:8040")
    called = False

    def complete(**_kwargs: object) -> str:
        nonlocal called
        called = True
        return '{"pull": false, "filters": {}, "say": "Открываю дашборд как он сейчас настроен."}'

    plan = plan_dashboard_phrase("открой дашборд", _LIVE_CATALOG, complete)
    assert called is True
    assert plan["reply"] == "Открываю дашборд как он сейчас настроен."
    assert plan["pull"] is True
    assert plan["filters"] == {
        "trendtype": "cumulative",
        "typenum": 1,
        "month": 2,
        "year": 2025,
        "vtypevd": "0000000",
    }
    assert plan["viewer"].endswith("/open")


def test_named_filter_overrides_only_that_catalog_value() -> None:
    def complete(**_kwargs: object) -> str:
        return '{"pull": true, "filters": {"Единицы": "млн.", "Месяц": "Март"}}'

    plan = plan_dashboard_phrase("открой дашборд за март, млн.", _LIVE_CATALOG, complete)
    assert plan["filters"] == {
        "trendtype": "cumulative",
        "typenum": 1000000,
        "month": 3,
        "year": 2025,
        "vtypevd": "0000000",
    }


class _Poster:
    def __init__(self, status: int = 200, url: str = "") -> None:
        self.status = status
        self.url = url
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[str] = []

    def post(self, url: str, json: dict | None = None, **_kwargs):
        self.posts.append((url, json or {}))
        body = {"ok": True, "url": self.url} if self.url else {}
        return _Resp(self.status, body)

    def get(self, url: str, **_kwargs):
        self.gets.append(url)
        return _Resp(200, {"mrt": "last.mrt", "filters": [{"name": "month", "value": "2"}]})


class _Resp:
    def __init__(self, status: int, body: dict) -> None:
        self.status_code = status
        self._body = body

    def json(self) -> dict:
        return self._body


def test_finish_posts_the_open_body_then_points_at_the_viewer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_SERVICE_URL", "http://127.0.0.1:8040")
    poster = _Poster()
    plan = finish_dashboard_phrase(
        {
            "pull": True,
            "filters": {"month": 2, "vtypevd": "0000000"},
            "reply": "Сейчас открою.",
            "viewer": "http://127.0.0.1:8040/open?filters=%7B%7D",
        },
        "http://127.0.0.1:8040",
        poster,
    )
    assert poster.posts == [
        (
            "http://127.0.0.1:8040/open?open=0",
            {"filters": {"month": 2, "vtypevd": "0000000"}},
        )
    ]
    assert plan["viewer"] == "http://127.0.0.1:8040/open"


def test_finish_uses_the_url_the_service_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_SERVICE_URL", "http://127.0.0.1:8040")
    poster = _Poster(url="http://localhost:8040/open")
    plan = finish_dashboard_phrase(
        {"pull": True, "filters": {"month": 2}, "reply": "Сейчас открою."},
        "http://127.0.0.1:8040",
        poster,
    )
    assert plan["viewer"] == "http://localhost:8040/open"


def test_open_named_dashboard_reads_filters_then_posts_that_mrt() -> None:
    class _Client:
        def __init__(self) -> None:
            self.gets: list[str] = []
            self.posts: list[tuple[str, dict]] = []

        def get(self, url: str, **_kwargs):
            self.gets.append(url)
            return _Resp(
                200,
                {
                    "mrt": "plan.mrt",
                    "filters": [{"name": "month", "value": "2"}],
                },
            )

        def post(self, url: str, json: dict | None = None, **_kwargs):
            self.posts.append((url, json or {}))
            if url.endswith("/filters"):
                return _Resp(
                    200,
                    {
                        "mrt": "plan.mrt",
                        "filters": [{"name": "month", "value": "2"}],
                    },
                )
            return _Resp(200, {"ok": True, "url": "http://127.0.0.1:8040/open"})

    client = _Client()
    plan = open_named_dashboard("http://127.0.0.1:8040", "plan.mrt", client)
    assert client.posts[0] == ("http://127.0.0.1:8040/filters", {"mrt": "plan.mrt"})
    assert client.posts[1][1]["mrt"] == "plan.mrt"
    assert "month" in client.posts[1][1]["filters"]
    assert plan["viewer"] == "http://127.0.0.1:8040/open"
    assert plan["mrt"] == "plan.mrt"


def test_fetch_dashboards_keeps_mrt_names() -> None:
    class _Client:
        def get(self, url: str, **_kwargs):
            assert url.endswith("/dashboards")
            return _Resp(
                200,
                {
                    "dashboards": [
                        {"name": "plan.mrt", "title": "plan", "preview": "plan.png"},
                        {"name": "bare.mrt", "title": "bare", "preview": "../x.png"},
                        {"name": "note.txt"},
                    ]
                },
            )

    rows = fetch_dashboards("http://127.0.0.1:8040", _Client())
    assert rows == [
        {"name": "plan.mrt", "title": "plan", "preview": "plan.png"},
        {"name": "bare.mrt", "title": "bare"},
    ]


def test_fetch_dashboard_preview_reads_the_matching_picture() -> None:
    class _Client:
        def get(self, url: str, **_kwargs):
            assert "mrt=plan.mrt" in url
            response = _Resp(200, {})
            response.content = b"\x89PNG"
            response.headers = {"content-type": "image/png"}
            return response

    content, media = fetch_dashboard_preview("http://127.0.0.1:8040", "plan.mrt", _Client())
    assert content.startswith(b"\x89PNG")
    assert media == "image/png"


def test_fetch_filter_catalog_calls_the_filters_endpoint() -> None:
    poster = _Poster()
    catalog = fetch_filter_catalog("http://127.0.0.1:8040", poster)
    assert poster.gets == ["http://127.0.0.1:8040/filters"]
    assert catalog["mrt"] == "last.mrt"


def test_finish_does_not_post_when_the_phrase_is_not_a_pull() -> None:
    poster = _Poster()
    plan = finish_dashboard_phrase({"pull": False}, "http://127.0.0.1:8040", poster)
    assert poster.posts == []
    assert plan == {"pull": False}


def test_read_filter_catalog_uses_the_local_file(tmp_path, monkeypatch) -> None:
    catalog = tmp_path / "dashboard_filters.json"
    catalog.write_text(
        '{"filters": [{"name": "month"}], "mrt": "last.mrt"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("DASHBOARD_FILTERS_FILE", str(catalog))
    assert read_filter_catalog()["mrt"] == "last.mrt"
    monkeypatch.setenv("DASHBOARD_FILTERS_FILE", str(tmp_path / "missing.json"))
    assert read_filter_catalog() is None


def test_files_from_shot_refuses_a_bare_remote_path() -> None:
    payload = {"ok": True, "png": {"name": "screen.png", "path": "/only/on/his/disk.png"}}
    with pytest.raises(DashboardRemoteError) as caught:
        files_from_shot(payload, fetch_named=lambda _name: None)
    assert "той же машине" in caught.value.message
    assert caught.value.code == "no_bytes"


def test_open_named_dashboard_supports_zero_filters_and_lan_path() -> None:
    class _ZeroFilterClient:
        def __init__(self) -> None:
            self.posts: list[tuple[str, dict]] = []

        def get(self, url: str, **_kwargs):
            assert "mrt=plain.mrt" in url
            return _Resp(200, {"mrt": "plain.mrt", "filters": [], "count": 0})

        def post(self, url: str, json=None, **_kwargs):
            self.posts.append((url, dict(json or {})))
            if url.endswith("/filters"):
                return _Resp(200, {"mrt": "plain.mrt", "filters": [], "count": 0})
            return _Resp(
                200,
                {
                    "ok": True,
                    "url": "http://0.0.0.0:8040/open?mrt=plain.mrt&rf=tok1",
                    "path": "/open?mrt=plain.mrt&rf=tok1",
                },
            )

    c = _ZeroFilterClient()
    opened = open_named_dashboard("http://192.168.1.50:8040", "plain.mrt", c)
    assert opened["mrt"] == "plain.mrt"
    assert opened["filters"] == {}
    assert opened["viewer"] == "http://192.168.1.50:8040/open?mrt=plain.mrt&rf=tok1"
    assert c.posts == [
        ("http://192.168.1.50:8040/filters", {"mrt": "plain.mrt"}),
        ("http://192.168.1.50:8040/open?open=0", {"filters": {}, "mrt": "plain.mrt"}),
    ]


def test_phrase_has_respects_numeric_and_word_boundaries() -> None:
    from case3.dashboard_remote import _phrase_has

    assert _phrase_has("выручка 1000000 рублей", "100") is False
    assert _phrase_has("данные за 2025 год", "2025") is True
    assert _phrase_has("февраль 25", "2025") is True
    assert _phrase_has("код 125", "2025") is False


def test_fetch_shot_payload_forwards_mrt_param() -> None:
    from case3.dashboard_remote import fetch_shot_payload

    seen: list[str] = []

    class _Client:
        def get(self, url: str, **_kwargs):
            seen.append(url)
            return _Resp(200, {"ok": True})

    body = fetch_shot_payload("http://127.0.0.1:8040", _Client(), mrt="a.mrt")
    assert body == {"ok": True}
    assert seen == ["http://127.0.0.1:8040/shot?mrt=a.mrt"]


def test_fetch_filter_catalog_with_question_uses_post_and_propagates_picked_mrt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_SERVICE_URL", "http://127.0.0.1:8040")

    class _Client:
        def __init__(self) -> None:
            self.gets: list[str] = []
            self.posts: list[tuple[str, dict]] = []

        def get(self, url: str, **_kwargs):
            self.gets.append(url)
            return _Resp(200, {"mrt": "fallback.mrt", "filters": []})

        def post(self, url: str, json=None, **_kwargs):
            self.posts.append((url, dict(json or {})))
            if url.endswith("/filters"):
                return _Resp(
                    200,
                    {
                        "mrt": "revenue.mrt",
                        "dashboard": {"mrt": "revenue.mrt", "description": "Выручка"},
                        "filters": [
                            {
                                "name": "month",
                                "alias": "Месяц",
                                "value": "1",
                                "choices": [
                                    {"key": "1", "value": "Январь"},
                                    {"key": "2", "value": "Февраль"},
                                ],
                            }
                        ],
                        "result": {"month": "2"},
                        "path": "/open?mrt=revenue.mrt&rf=abc",
                        "url": "http://127.0.0.1:8040/open?mrt=revenue.mrt&rf=abc",
                    },
                )
            if "/open" in url:
                return _Resp(
                    200,
                    {
                        "ok": True,
                        "mrt": (json or {}).get("mrt"),
                        "path": "/open?mrt=revenue.mrt&rf=xyz",
                    },
                )
            return _Resp(404, {})

    c = _Client()
    cat = fetch_filter_catalog("http://127.0.0.1:8040", c, question="открой выручку за февраль")
    assert c.posts[0][0] == "http://127.0.0.1:8040/filters"
    assert cat["mrt"] == "revenue.mrt"

    plan = plan_dashboard_phrase(
        "открой дашборд выручки за февраль",
        cat,
        lambda **_k: '{"pull": true, "filters": {"Месяц": "Февраль"}, "say": "Открываю выручку за февраль."}',
    )
    assert plan["mrt"] == "revenue.mrt"
    assert plan["filters"] == {"month": 2}
    done = finish_dashboard_phrase(plan, "http://127.0.0.1:8040", c)
    assert done["mrt"] == "revenue.mrt"
    assert c.posts[-1][1]["mrt"] == "revenue.mrt"
    assert done["viewer"] == "http://127.0.0.1:8040/open?mrt=revenue.mrt&rf=xyz"


def test_plan_dashboard_phrase_adopts_all_catalog_result_params() -> None:
    catalog = {
        "mrt": "revenue.mrt",
        "filters": [
            {
                "name": "month",
                "alias": "Месяц",
                "value": "1",
                "choices": [
                    {"key": "1", "value": "Январь"},
                    {"key": "2", "value": "Февраль"},
                ],
            },
            {
                "name": "region",
                "alias": "Регион",
                "value": "10",
                "choices": [
                    {"key": "10", "value": "Минск"},
                    {"key": "99", "value": "Брест"},
                ],
            },
        ],
        "result": {"month": "2", "region": "99"},
    }
    plan = plan_dashboard_phrase(
        "открой дашборд выручки за февраль",
        catalog,
        lambda **_k: '{"pull": true, "filters": {}, "say": "Открываю за февраль."}',
    )
    assert plan["pull"] is True
    assert plan["mrt"] == "revenue.mrt"
    assert plan["filters"] == {"month": 2, "region": 99}


def test_plan_and_finish_forward_full_stimulsoft_result_not_present_in_filters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DASHBOARD_SERVICE_URL", "http://127.0.0.1:8040")
    catalog = {
        "count": 5,
        "dashboard": {
            "description": "## Поступления в бюджет.mrt\n...",
            "mrt": "Поступления в бюджет.mrt",
            "mrt_path": "D:\\dahboard\\dash_prod\\dash\\dashboards\\Поступления в бюджет.mrt",
        },
        "filters": [
            {
                "alias": "Год",
                "choices": [
                    {"key": "2023", "value": "2023"},
                    {"key": "2024", "value": "2024"},
                    {"key": "2025", "value": "2025"},
                    {"key": "2026", "value": "2026"},
                ],
                "name": "year",
                "value": "2026",
            }
        ],
        "result": {
            "month": "3",
            "trendtype": "cumulative",
            "typenum": "1000000",
            "vtypevd": "0000000",
            "year": "2025",
        },
    }
    plan = plan_dashboard_phrase(
        "открой анализ за февраль 2025",
        catalog,
        lambda **_k: '{"pull": true, "filters": {"year": "2025"}, "say": "Открываю поступления за февраль 2025."}',
    )
    assert plan["pull"] is True
    assert plan["mrt"] == "Поступления в бюджет.mrt"
    assert plan["filters"] == {
        "year": 2025,
        "month": 3,
        "trendtype": "cumulative",
        "typenum": 1000000,
        "vtypevd": "0000000",
    }
    poster = _Poster(url="http://127.0.0.1:8040/open?mrt=ok")
    done = finish_dashboard_phrase(plan, "http://127.0.0.1:8040", poster)
    assert poster.posts == [
        (
            "http://127.0.0.1:8040/open?open=0",
            {
                "filters": {
                    "year": 2025,
                    "month": 3,
                    "trendtype": "cumulative",
                    "typenum": 1000000,
                    "vtypevd": "0000000",
                },
                "mrt": "Поступления в бюджет.mrt",
            },
        )
    ]
    assert done["viewer"] == "http://127.0.0.1:8040/open?mrt=ok"


def test_finish_dashboard_phrase_calls_post_open_when_zero_filters() -> None:
    poster = _Poster(url="http://127.0.0.1:8040/open?mrt=plain.mrt")
    done = finish_dashboard_phrase(
        {"pull": True, "filters": {}, "mrt": "plain.mrt", "reply": "Открываю."},
        "http://127.0.0.1:8040",
        poster,
    )
    assert poster.posts == [
        ("http://127.0.0.1:8040/open?open=0", {"filters": {}, "mrt": "plain.mrt"})
    ]
    assert done["viewer"] == "http://127.0.0.1:8040/open?mrt=plain.mrt"


def test_fetch_filter_catalog_falls_back_when_question_llm_fails() -> None:
    class _Client:
        def __init__(self) -> None:
            self.posts: list[dict] = []

        def post(self, url: str, json=None, headers=None):  # noqa: A002
            body = dict(json or {})
            self.posts.append(body)
            if "question" in body:
                return _Resp(500, {"count": 0, "filters": [], "error": "Задай LLM_MODEL в .env"})
            return _Resp(200, {"count": 1, "filters": [{"name": "Year", "value": "2025"}]})

    c = _Client()
    cat = fetch_filter_catalog("http://127.0.0.1:8040", c, question="покажи за 2025")
    assert c.posts == [{"question": "покажи за 2025"}, {}]
    assert cat["count"] == 1
    assert cat["filters"][0]["name"] == "Year"


def test_fetch_dashboards_probes_preview_when_only_mrt_array_returned() -> None:
    class _Client:
        def get(self, url: str, **_kwargs):
            assert url.endswith("/dashboards")
            return _Resp(200, {"ok": True, "mrt": ["plan.mrt", "plain.mrt"]})

        def head(self, url: str, **_kwargs):
            if "mrt=plan.mrt" in url:
                return _Resp(200, {})
            return _Resp(404, {})

    rows = fetch_dashboards("http://127.0.0.1:8040", _Client())
    assert rows == [
        {"name": "plan.mrt", "title": "plan", "preview": "plan.png"},
        {"name": "plain.mrt", "title": "plain"},
    ]
