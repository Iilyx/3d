from case3.render import warmup_docker, is_docker_warmed


def test_docker_warmup_sync(monkeypatch) -> None:
    # Test synchronous docker warmup execution
    # If docker and case-3:tex exist, it succeeds; if mock or missing, it handles cleanly without throwing
    res = warmup_docker(background=False)
    assert isinstance(res, bool)


def test_docker_warmup_background() -> None:
    # Test background thread warmup starts cleanly
    res = warmup_docker(background=True)
    assert res is True
