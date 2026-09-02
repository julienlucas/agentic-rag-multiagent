from backend.utils.resilience import call_with_backoff, is_rate_limit, retry_after


class _Http(Exception):
    def __init__(self, status, headers=None):
        super().__init__(f"http {status}")
        self.status_code = status
        if headers is not None:
            self.raw_response = type("R", (), {"headers": headers})()


def test_is_rate_limit_from_status_message_and_cause():
    assert is_rate_limit(_Http(429))
    assert is_rate_limit(RuntimeError("Too Many Requests"))
    assert is_rate_limit(RuntimeError("service_tier_capacity_exceeded"))
    wrapped = RuntimeError("wrapper")
    wrapped.__cause__ = _Http(429)
    assert is_rate_limit(wrapped)
    assert not is_rate_limit(ValueError("boom"))
    assert not is_rate_limit(_Http(500))


def test_retry_after_reads_header_through_cause_chain():
    inner = _Http(429, headers={"Retry-After": "7"})
    outer = RuntimeError("wrapper")
    outer.__cause__ = inner
    assert retry_after(outer) == 7.0
    assert retry_after(_Http(429, headers={"Retry-After": "n/a"})) is None
    assert retry_after(ValueError("x")) is None


def test_call_with_backoff_retries_then_succeeds(monkeypatch):
    import backend.utils.resilience as res

    monkeypatch.setattr(res.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _Http(429)
        return "ok"

    assert call_with_backoff(flaky, "test", attempts=5, base_delay=0, log=lambda m: None) == "ok"
    assert calls["n"] == 3


def test_call_with_backoff_does_not_retry_other_errors(monkeypatch):
    import pytest
    import backend.utils.resilience as res

    monkeypatch.setattr(res.time, "sleep", lambda s: None)
    with pytest.raises(ValueError):
        call_with_backoff(lambda: (_ for _ in ()).throw(ValueError("x")), "test", attempts=3, log=lambda m: None)
