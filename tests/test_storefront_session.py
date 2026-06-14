import datetime as dt
from storefront.session import sign, verify


def test_sign_then_verify_roundtrip():
    now = dt.datetime(2026, 6, 1, 12, 0, 0)
    token = sign({"email": "a@b.com"}, secret="s3cret", now=now)
    data = verify(token, secret="s3cret", max_age=3600,
                  now=now + dt.timedelta(seconds=60))
    assert data["email"] == "a@b.com"


def test_tampered_token_rejected():
    now = dt.datetime(2026, 6, 1, 12, 0, 0)
    token = sign({"email": "a@b.com"}, secret="s3cret", now=now)
    assert verify(token[:-2] + "xx", secret="s3cret", max_age=3600, now=now) is None


def test_wrong_secret_rejected():
    now = dt.datetime(2026, 6, 1, 12, 0, 0)
    token = sign({"email": "a@b.com"}, secret="s3cret", now=now)
    assert verify(token, secret="other", max_age=3600, now=now) is None


def test_expired_session_rejected():
    now = dt.datetime(2026, 6, 1, 12, 0, 0)
    token = sign({"email": "a@b.com"}, secret="s3cret", now=now)
    assert verify(token, secret="s3cret", max_age=3600,
                  now=now + dt.timedelta(seconds=3601)) is None
