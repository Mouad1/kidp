import base64
import datetime as dt
import hashlib
import hmac
import json


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign(payload: dict, secret: str, now: dt.datetime) -> str:
    body = dict(payload)
    body["_iat"] = int(now.timestamp())
    raw = _b64e(json.dumps(body, sort_keys=True).encode())
    sig = _b64e(hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest())
    return f"{raw}.{sig}"


def verify(token: str, secret: str, max_age: int, now: dt.datetime) -> dict | None:
    try:
        raw, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = _b64e(hmac.new(secret.encode(), raw.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        body = json.loads(_b64d(raw))
    except (ValueError, json.JSONDecodeError):
        return None
    iat = body.get("_iat", 0)
    if now.timestamp() - iat > max_age:
        return None
    body.pop("_iat", None)
    return body
