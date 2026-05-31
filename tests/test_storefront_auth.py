import datetime as dt
from storefront.auth import (
    generate_code, request_code, verify_code, AuthStore, FakeCodeSender,
)


def test_generate_code_is_six_digits():
    for _ in range(50):
        c = generate_code()
        assert len(c) == 6 and c.isdigit()


def test_request_then_verify_succeeds(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sender = FakeCodeSender()
    now = dt.datetime(2026, 6, 1, 12, 0, 0)
    request_code("a@b.com", now=now, code_sender=sender, store=store, ttl_seconds=600)
    assert sender.sent[0][0] == "a@b.com"
    code = sender.sent[0][1]
    assert verify_code("a@b.com", code, now=now + dt.timedelta(seconds=30), store=store)


def test_expired_code_fails(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sender = FakeCodeSender()
    now = dt.datetime(2026, 6, 1, 12, 0, 0)
    request_code("a@b.com", now=now, code_sender=sender, store=store, ttl_seconds=600)
    code = sender.sent[0][1]
    assert not verify_code("a@b.com", code, now=now + dt.timedelta(seconds=601), store=store)


def test_wrong_code_fails_and_is_rate_limited(tmp_path):
    store = AuthStore(tmp_path / "auth.json")
    sender = FakeCodeSender()
    now = dt.datetime(2026, 6, 1, 12, 0, 0)
    request_code("a@b.com", now=now, code_sender=sender, store=store, ttl_seconds=600)
    for _ in range(5):
        assert not verify_code("a@b.com", "000000", now=now, store=store)
    code = sender.sent[0][1]
    assert not verify_code("a@b.com", code, now=now, store=store)


def test_smtp_sender_builds_message(monkeypatch):
    from storefront.auth import SmtpCodeSender
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port): sent["addr"] = (host, port)
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): sent["tls"] = True
        def login(self, u, p): sent["login"] = (u, p)
        def send_message(self, msg): sent["msg"] = msg

    monkeypatch.setattr("storefront.auth.smtplib.SMTP", FakeSMTP)
    s = SmtpCodeSender(host="smtp.test", port=587, username="u", password="p",
                       from_addr="no-reply@test")
    s.send("a@b.com", "123456")
    assert sent["addr"] == ("smtp.test", 587)
    assert sent["msg"]["To"] == "a@b.com"
    assert "123456" in sent["msg"].get_content()
