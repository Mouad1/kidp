# StoryForge Storefront (Workstream C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a customer-facing storefront where visitors browse published stories, personalize one with their child's name + photo, preview the result and cover, see the price, authenticate with an emailed one-time code, and check out via a (stubbed, pluggable) payment provider — all in the same dashboard app under a separate `/store` route.

**Architecture:** A new `storefront/` package holds pure, network-free logic behind dependency-injection seams (matching the existing `ImageGenerator` Protocol pattern): email one-time-code auth (`auth.py`), HMAC signed-cookie sessions (`session.py`), catalog reads (`catalog.py`), and a payment interface (`payment.py`). `dashboard/app.py` mounts thin `/store` routes that call these modules. No new third-party dependencies: signing uses stdlib `hmac`/`hashlib`/`secrets`, email uses stdlib `smtplib`, payment is an injectable interface stubbed for the first iteration. Real Stripe and SMTP wiring is config-driven and left disabled by default.

**Tech Stack:** Python 3.10+, FastAPI/Starlette, Jinja2 templates, Tailwind CDN, stdlib crypto/email. Tests via `python3 -m pytest`. No new deps.

---

## File Structure

- `storefront/__init__.py` — package exports.
- `storefront/auth.py` — one-time-code core: `generate_code`, `CodeRecord`, `CodeSender` Protocol, `FakeCodeSender`, `SmtpCodeSender`, `AuthStore` (file-backed JSON), `request_code`, `verify_code`. Clock + sender injected.
- `storefront/session.py` — `sign(payload, secret)`, `verify(token, secret, max_age, now)` using HMAC-SHA256; no external dep.
- `storefront/catalog.py` — `list_catalog()` reads `books/*/config.py` via `read_config`, returns only entries flagged published, with title/cover/base price.
- `storefront/payment.py` — `PaymentProvider` Protocol, `CheckoutSession` dataclass, `StubPaymentProvider`, factory `get_payment_provider(settings)`.
- `dashboard/app.py` — mount `/store` routes (catalog, personalize, auth request/verify, checkout) + `_store_*` provider seams (overridden in tests).
- `dashboard/templates/store_catalog.html`, `store_personalize.html` — customer UI.
- `pipeline/config_io.py` — add `published` to the read/write mapping (`PUBLISHED` constant).
- `settings.example.json` — add `storefront` block (session secret name, smtp config, payment provider = "stub").
- Tests: `tests/test_storefront_auth.py`, `tests/test_storefront_session.py`, `tests/test_storefront_catalog.py`, `tests/test_storefront_payment.py`, `tests/test_storefront_api.py`.

---

## Task 1: Email one-time-code auth core

**Files:**
- Create: `storefront/auth.py`
- Test: `tests/test_storefront_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storefront_auth.py
import datetime as dt
import pytest
from storefront.auth import (
    generate_code, request_code, verify_code, AuthStore, FakeCodeSender,
)


def _clock(t):
    return lambda: t


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
    # correct code now rejected because attempts exhausted
    code = sender.sent[0][1]
    assert not verify_code("a@b.com", code, now=now, store=store)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'storefront'`

- [ ] **Step 3: Write minimal implementation**

```python
# storefront/auth.py
import datetime as dt
import hashlib
import hmac
import json
import pathlib
import secrets
from dataclasses import dataclass, asdict
from typing import Callable, Protocol

MAX_ATTEMPTS = 5


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _hash(email: str, code: str, salt: str) -> str:
    return hmac.new(salt.encode(), f"{email}:{code}".encode(), hashlib.sha256).hexdigest()


class CodeSender(Protocol):
    def send(self, email: str, code: str) -> None: ...


class FakeCodeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, email: str, code: str) -> None:
        self.sent.append((email, code))


@dataclass
class CodeRecord:
    email: str
    code_hash: str
    salt: str
    expires_at: str  # ISO
    attempts: int = 0


class AuthStore:
    """File-backed JSON store: email -> CodeRecord. Good enough for low volume."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data))

    def put(self, rec: CodeRecord) -> None:
        data = self._load()
        data[rec.email] = asdict(rec)
        self._save(data)

    def get(self, email: str) -> CodeRecord | None:
        raw = self._load().get(email)
        return CodeRecord(**raw) if raw else None

    def delete(self, email: str) -> None:
        data = self._load()
        data.pop(email, None)
        self._save(data)


def request_code(email: str, now: dt.datetime, code_sender: CodeSender,
                 store: AuthStore, ttl_seconds: int = 600) -> None:
    code = generate_code()
    salt = secrets.token_hex(16)
    rec = CodeRecord(
        email=email,
        code_hash=_hash(email, code, salt),
        salt=salt,
        expires_at=(now + dt.timedelta(seconds=ttl_seconds)).isoformat(),
    )
    store.put(rec)
    code_sender.send(email, code)


def verify_code(email: str, code: str, now: dt.datetime, store: AuthStore) -> bool:
    rec = store.get(email)
    if rec is None:
        return False
    if rec.attempts >= MAX_ATTEMPTS:
        return False
    if now > dt.datetime.fromisoformat(rec.expires_at):
        return False
    candidate = _hash(email, code, rec.salt)
    if hmac.compare_digest(candidate, rec.code_hash):
        store.delete(email)
        return True
    rec.attempts += 1
    store.put(rec)
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_auth.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add storefront/auth.py tests/test_storefront_auth.py
git commit -m "feat(storefront): email one-time-code auth core (DI sender + clock)"
```

---

## Task 2: SMTP code sender (real sender, network behind config)

**Files:**
- Modify: `storefront/auth.py`
- Test: `tests/test_storefront_auth.py`

- [ ] **Step 1: Write the failing test** (append)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_auth.py::test_smtp_sender_builds_message -v`
Expected: FAIL with `ImportError: cannot import name 'SmtpCodeSender'`

- [ ] **Step 3: Write minimal implementation** (append to `storefront/auth.py`)

```python
import smtplib
from email.message import EmailMessage


class SmtpCodeSender:
    def __init__(self, host: str, port: int, username: str, password: str,
                 from_addr: str, use_tls: bool = True):
        self.host, self.port = host, port
        self.username, self.password = username, password
        self.from_addr, self.use_tls = from_addr, use_tls

    def send(self, email: str, code: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = "Your StoryForge confirmation code"
        msg["From"] = self.from_addr
        msg["To"] = email
        msg.set_content(f"Your confirmation code is {code}. It expires in 10 minutes.")
        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password)
            server.send_message(msg)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_auth.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add storefront/auth.py tests/test_storefront_auth.py
git commit -m "feat(storefront): SMTP code sender (config-driven)"
```

---

## Task 3: Signed-cookie session

**Files:**
- Create: `storefront/session.py`
- Test: `tests/test_storefront_session.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storefront_session.py
import datetime as dt
import pytest
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'storefront.session'`

- [ ] **Step 3: Write minimal implementation**

```python
# storefront/session.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_session.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add storefront/session.py tests/test_storefront_session.py
git commit -m "feat(storefront): HMAC signed-cookie session (stdlib, no deps)"
```

---

## Task 4: Published flag in config I/O

**Files:**
- Modify: `pipeline/config_io.py` (read mapping + write template)
- Test: `tests/test_config_io.py` (append)

- [ ] **Step 1: Write the failing test** (append)

```python
def test_published_flag_roundtrips(tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    data = {
        "category": "story", "story_format": "colored", "story_layout": "top_bottom",
        "languages": ["en"], "story_base_prompt": "", "intro_text": "",
        "values_learned": "", "pages": [], "title": "T", "subtitle": "",
        "author": "A", "images_folder": "x", "characters": [], "published": True,
    }
    cio.write_config("demo", data)
    out = cio.read_config("demo")
    assert out["published"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config_io.py::test_published_flag_roundtrips -v`
Expected: FAIL with `KeyError: 'published'` or `AssertionError`

- [ ] **Step 3: Implement**

In `read_config`, add `published` to the dict it returns: `"published": getattr(cfg_module, "PUBLISHED", False)`.
In `write_config`, emit `PUBLISHED = {data.get("published", False)!r}` alongside the other constants.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config_io.py::test_published_flag_roundtrips -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/config_io.py tests/test_config_io.py
git commit -m "feat(config): persist PUBLISHED flag for storefront catalog"
```

---

## Task 5: Catalog module

**Files:**
- Create: `storefront/catalog.py`
- Test: `tests/test_storefront_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storefront_catalog.py
from storefront.catalog import list_catalog, CatalogEntry


def fake_reader(name):
    data = {
        "alpha": {"title": "Alpha", "published": True, "pages": [1, 2, 3, 4],
                  "category": "story"},
        "beta": {"title": "Beta", "published": False, "pages": [1, 2],
                 "category": "story"},
    }
    return data[name]


def test_only_published_books_listed():
    entries = list_catalog(["alpha", "beta"], read_fn=fake_reader)
    assert [e.slug for e in entries] == ["alpha"]
    assert isinstance(entries[0], CatalogEntry)
    assert entries[0].title == "Alpha"
    assert entries[0].page_count == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# storefront/catalog.py
from dataclasses import dataclass
from typing import Callable


@dataclass
class CatalogEntry:
    slug: str
    title: str
    page_count: int
    category: str


def list_catalog(book_names: list[str], read_fn: Callable[[str], dict]) -> list[CatalogEntry]:
    out: list[CatalogEntry] = []
    for name in book_names:
        cfg = read_fn(name)
        if not cfg.get("published"):
            continue
        out.append(CatalogEntry(
            slug=name,
            title=cfg.get("title", name),
            page_count=len(cfg.get("pages", [])),
            category=cfg.get("category", "story"),
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_catalog.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add storefront/catalog.py tests/test_storefront_catalog.py
git commit -m "feat(storefront): catalog lists published books"
```

---

## Task 6: Payment interface (stub provider)

**Files:**
- Create: `storefront/payment.py`
- Test: `tests/test_storefront_payment.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storefront_payment.py
from storefront.payment import StubPaymentProvider, CheckoutSession, get_payment_provider


def test_stub_provider_creates_pending_session():
    p = StubPaymentProvider()
    s = p.create_checkout(amount=530, currency="USD", reference="order-1")
    assert isinstance(s, CheckoutSession)
    assert s.status == "pending"
    assert s.amount == 530
    assert s.reference == "order-1"
    assert s.url.endswith("order-1")


def test_factory_defaults_to_stub():
    p = get_payment_provider({"payment_provider": "stub"})
    assert isinstance(p, StubPaymentProvider)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_payment.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# storefront/payment.py
from dataclasses import dataclass
from typing import Protocol


@dataclass
class CheckoutSession:
    reference: str
    amount: int  # minor units (cents)
    currency: str
    status: str  # "pending" | "paid" | "failed"
    url: str


class PaymentProvider(Protocol):
    def create_checkout(self, amount: int, currency: str, reference: str) -> CheckoutSession: ...


class StubPaymentProvider:
    """No real charge. Returns a pending session pointing at an internal mock page."""

    def create_checkout(self, amount: int, currency: str, reference: str) -> CheckoutSession:
        return CheckoutSession(
            reference=reference, amount=amount, currency=currency,
            status="pending", url=f"/store/checkout/mock/{reference}",
        )


def get_payment_provider(settings: dict) -> PaymentProvider:
    provider = (settings or {}).get("payment_provider", "stub")
    if provider == "stub":
        return StubPaymentProvider()
    raise ValueError(f"Unsupported payment provider: {provider!r}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_payment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add storefront/payment.py tests/test_storefront_payment.py
git commit -m "feat(storefront): pluggable payment interface + stub provider"
```

---

## Task 7: Package exports + storefront settings block

**Files:**
- Create: `storefront/__init__.py`
- Modify: `settings.example.json`
- Test: `tests/test_storefront_payment.py` (append a settings sanity test)

- [ ] **Step 1: Write the failing test** (append)

```python
def test_settings_example_has_storefront_block():
    import json, pathlib
    root = pathlib.Path(__file__).parent.parent
    data = json.loads((root / "settings.example.json").read_text())
    assert "storefront" in data
    sf = data["storefront"]
    for key in ("session_secret", "payment_provider", "smtp"):
        assert key in sf
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_payment.py::test_settings_example_has_storefront_block -v`
Expected: FAIL (no `storefront` key)

- [ ] **Step 3: Implement**

`storefront/__init__.py`:

```python
from storefront.auth import (
    generate_code, request_code, verify_code, AuthStore,
    CodeSender, FakeCodeSender, SmtpCodeSender,
)
from storefront.session import sign, verify
from storefront.catalog import list_catalog, CatalogEntry
from storefront.payment import (
    PaymentProvider, CheckoutSession, StubPaymentProvider, get_payment_provider,
)

__all__ = [
    "generate_code", "request_code", "verify_code", "AuthStore",
    "CodeSender", "FakeCodeSender", "SmtpCodeSender",
    "sign", "verify", "list_catalog", "CatalogEntry",
    "PaymentProvider", "CheckoutSession", "StubPaymentProvider", "get_payment_provider",
]
```

Add to `settings.example.json` (after `pricing`):

```json
"storefront": {
    "session_secret": "CHANGE_ME_TO_A_LONG_RANDOM_STRING",
    "payment_provider": "stub",
    "smtp": {
        "host": "",
        "port": 587,
        "username": "",
        "password": "",
        "from_addr": "no-reply@example.com",
        "use_tls": true
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_payment.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add storefront/__init__.py settings.example.json tests/test_storefront_payment.py
git commit -m "feat(storefront): package exports + settings template"
```

---

## Task 8: Storefront routes — catalog + auth + personalize + checkout

**Files:**
- Modify: `dashboard/app.py`
- Create: `dashboard/templates/store_catalog.html`, `dashboard/templates/store_personalize.html`
- Test: `tests/test_storefront_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storefront_api.py
import pytest
from fastapi.testclient import TestClient
import dashboard.app as appmod

client = TestClient(appmod.app)


@pytest.fixture(autouse=True)
def fake_seams(monkeypatch, tmp_path):
    from storefront.auth import FakeCodeSender, AuthStore
    sender = FakeCodeSender()
    monkeypatch.setattr(appmod, "_store_code_sender", lambda: sender)
    monkeypatch.setattr(appmod, "_store_auth_store", lambda: AuthStore(tmp_path / "auth.json"))
    monkeypatch.setattr(appmod, "_store_session_secret", lambda: "test-secret")
    monkeypatch.setattr(appmod, "_store_catalog_names", lambda: ["pub", "draft"])

    def fake_read(name):
        return {
            "pub": {"title": "Pub", "published": True, "pages": [1, 2], "category": "story"},
            "draft": {"title": "Draft", "published": False, "pages": [1], "category": "story"},
        }[name]

    monkeypatch.setattr(appmod, "_store_read_config", fake_read)
    return sender


def test_catalog_lists_only_published():
    r = client.get("/store")
    assert r.status_code == 200
    assert "Pub" in r.text
    assert "Draft" not in r.text


def test_auth_request_then_verify_sets_cookie(fake_seams):
    r = client.post("/store/auth/request", json={"email": "a@b.com"})
    assert r.status_code == 200
    code = fake_seams.sent[0][1]
    r2 = client.post("/store/auth/verify", json={"email": "a@b.com", "code": code})
    assert r2.status_code == 200
    assert "sf_session" in r2.cookies


def test_verify_wrong_code_401(fake_seams):
    client.post("/store/auth/request", json={"email": "a@b.com"})
    r = client.post("/store/auth/verify", json={"email": "a@b.com", "code": "000000"})
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_api.py -v`
Expected: FAIL (routes/seams not defined)

- [ ] **Step 3: Implement** (in `dashboard/app.py`, before the `if __name__` block)

Add seam helpers and routes:

```python
def _store_code_sender():
    from storefront.auth import SmtpCodeSender
    sf = _load_storefront_settings()
    smtp = sf.get("smtp", {})
    return SmtpCodeSender(
        host=smtp.get("host", ""), port=smtp.get("port", 587),
        username=smtp.get("username", ""), password=smtp.get("password", ""),
        from_addr=smtp.get("from_addr", "no-reply@example.com"),
        use_tls=smtp.get("use_tls", True),
    )


def _store_auth_store():
    from storefront.auth import AuthStore
    return AuthStore(ROOT / ".storefront" / "auth.json")


def _store_session_secret():
    return _load_storefront_settings().get("session_secret", "dev-insecure-secret")


def _store_catalog_names():
    return [p.parent.name for p in (ROOT / "books").glob("*/config.py")]


def _store_read_config(name):
    return read_config(name)


def _load_storefront_settings():
    settings_file = ROOT / "settings.json"
    if settings_file.exists():
        try:
            return json.loads(settings_file.read_text()).get("storefront", {})
        except (json.JSONDecodeError, OSError):
            pass
    return {}


@app.get("/store", response_class=HTMLResponse)
def store_catalog(request: Request):
    from storefront.catalog import list_catalog
    entries = list_catalog(_store_catalog_names(), read_fn=_store_read_config)
    return templates.TemplateResponse(
        request=request, name="store_catalog.html", context={"entries": entries})


@app.post("/store/auth/request")
def store_auth_request(payload: dict):
    import datetime as dt
    from storefront.auth import request_code
    email = (payload or {}).get("email", "").strip()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required.")
    request_code(email, now=dt.datetime.utcnow(),
                 code_sender=_store_code_sender(), store=_store_auth_store())
    return {"sent": True}


@app.post("/store/auth/verify")
def store_auth_verify(payload: dict):
    import datetime as dt
    from storefront.auth import verify_code
    from storefront.session import sign
    email = (payload or {}).get("email", "").strip()
    code = (payload or {}).get("code", "").strip()
    now = dt.datetime.utcnow()
    if not verify_code(email, code, now=now, store=_store_auth_store()):
        raise HTTPException(status_code=401, detail="Invalid or expired code.")
    token = sign({"email": email}, secret=_store_session_secret(), now=now)
    resp = JSONResponse({"verified": True})
    resp.set_cookie("sf_session", token, httponly=True, samesite="lax", max_age=86400)
    return resp


@app.get("/store/{slug}", response_class=HTMLResponse)
def store_personalize(request: Request, slug: str):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', slug):
        raise HTTPException(status_code=400, detail="Invalid slug")
    cfg = _store_read_config(slug)
    if not cfg.get("published"):
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse(
        request=request, name="store_personalize.html",
        context={"slug": slug, "title": cfg.get("title", slug)})
```

Add `JSONResponse` to the `from fastapi.responses import ...` line.

Create `dashboard/templates/store_catalog.html` (Tailwind grid of `entries`, each linking to `/store/{{ e.slug }}`) and `store_personalize.html` (linear wizard: email→code→name+photo→language/page-count→live price→"Validate & pay"). Reuse the `/api/pricing` and `/api/storyforge/*` endpoints from Workstream A/B.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_api.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py dashboard/templates/store_catalog.html dashboard/templates/store_personalize.html tests/test_storefront_api.py
git commit -m "feat(storefront): /store catalog, email-code auth, personalize routes"
```

---

## Task 9: Checkout (stubbed) + auth gate

**Files:**
- Modify: `dashboard/app.py`
- Test: `tests/test_storefront_api.py` (append)

- [ ] **Step 1: Write the failing test** (append)

```python
def test_checkout_requires_session(fake_seams):
    r = client.post("/store/pub/checkout",
                    json={"page_count": 16, "color": True, "paper_quality": "standard"})
    assert r.status_code == 401


def test_checkout_with_session_returns_pending(fake_seams):
    client.post("/store/auth/request", json={"email": "a@b.com"})
    code = fake_seams.sent[0][1]
    v = client.post("/store/auth/verify", json={"email": "a@b.com", "code": code})
    client.cookies.set("sf_session", v.cookies["sf_session"])
    r = client.post("/store/pub/checkout",
                    json={"page_count": 16, "color": True, "paper_quality": "standard"})
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_api.py -k checkout -v`
Expected: FAIL (route not defined)

- [ ] **Step 3: Implement**

```python
def _require_session(request: Request) -> dict:
    import datetime as dt
    from storefront.session import verify
    token = request.cookies.get("sf_session", "")
    data = verify(token, secret=_store_session_secret(), max_age=86400, now=dt.datetime.utcnow())
    if data is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return data


@app.post("/store/{slug}/checkout")
def store_checkout(slug: str, payload: dict, request: Request):
    from pipeline.pricing import compute_price
    from storefront.payment import get_payment_provider
    session = _require_session(request)
    cfg = _store_read_config(slug)
    if not cfg.get("published"):
        raise HTTPException(status_code=404, detail="Not found")
    pricing = _load_pricing_settings()
    quote = compute_price(
        page_count=int(payload.get("page_count", len(cfg.get("pages", [])))),
        color=bool(payload.get("color", True)),
        paper_quality=payload.get("paper_quality", "standard"),
        has_cover=True, settings=pricing,
    )
    amount = int(round(quote["price"] * 100))
    provider = get_payment_provider(_load_storefront_settings())
    ref = f"{slug}-{session['email']}-{int(__import__('time').time())}"
    s = provider.create_checkout(amount=amount, currency=quote["currency"], reference=ref)
    return {"status": s.status, "url": s.url, "amount": s.amount, "currency": s.currency}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_api.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py tests/test_storefront_api.py
git commit -m "feat(storefront): auth-gated stubbed checkout with live pricing"
```

---

## Task 10: Admin publish toggle

**Files:**
- Modify: `dashboard/app.py` (publish endpoint), `dashboard/templates/book.html` (toggle button)
- Test: `tests/test_storefront_api.py` (append)

- [ ] **Step 1: Write the failing test** (append)

```python
def test_publish_toggle_sets_flag(tmp_path, monkeypatch):
    written = {}
    monkeypatch.setattr(appmod, "_store_read_config",
                        lambda name: {"title": "X", "published": False, "pages": []})
    monkeypatch.setattr(appmod, "write_config", lambda name, data: written.update({name: data}))
    r = client.post("/api/storyforge/pub/publish", json={"published": True})
    assert r.status_code == 200
    assert written["pub"]["published"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_storefront_api.py::test_publish_toggle_sets_flag -v`
Expected: FAIL (route not defined)

- [ ] **Step 3: Implement**

```python
@app.post("/api/storyforge/{name}/publish")
def storyforge_publish(name: str, payload: dict):
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', name):
        raise HTTPException(status_code=400, detail="Invalid book name")
    cfg = _store_read_config(name)
    cfg["published"] = bool(payload.get("published", False))
    write_config(name, cfg)
    return {"published": cfg["published"]}
```

Add a "Publish to store" toggle in `book.html` calling this endpoint.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_storefront_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard/app.py dashboard/templates/book.html tests/test_storefront_api.py
git commit -m "feat(storefront): admin publish toggle"
```

---

## Task 11: Non-regression + docs

- [ ] **Step 1:** Run `python3 -m pytest tests/test_storefront_*.py -v` — all pass.
- [ ] **Step 2:** Run full suite `python3 -m pytest -q` — confirm no NEW failures (the pre-existing `test_config_io::test_read_config_returns_dict` failure is unrelated; Task 4 may incidentally affect it — verify and fix if our change is the cause).
- [ ] **Step 3:** Update `tasks/lessons.md` with any corrections and `BACKLOG.md` (move Workstream C items to done as completed).
- [ ] **Step 4:** Add `.storefront/` to `.gitignore` (runtime auth store must never be committed).
- [ ] **Step 5: Commit**

```bash
git add tasks/lessons.md BACKLOG.md .gitignore
git commit -m "docs: storefront lessons + backlog; ignore runtime auth store"
```

---

## Self-Review

**Spec coverage:**
- Catalog of published stories → Tasks 4, 5, 8, 10. ✓
- Personalize (name + photo, language, page count, live price) → Task 8 (reuses Workstream A/B endpoints). ✓
- Preview (pages + cover) → reuses existing `/api/storyforge/{name}/portrait` + `/cover`; surfaced in `store_personalize.html` (Task 8). ✓
- Email + confirmation code auth (free SMTP, pluggable sender, SMS deferred) → Tasks 1, 2, 8. ✓
- Session via signed cookie → Tasks 3, 8, 9. ✓
- Stripe payment (stubbed, pluggable) → Tasks 6, 9. ✓
- Admin `/book/<slug>` stays admin-only; customers use `/store` → Tasks 8, 10 (separate routes). ✓

**Deferred (own follow-up):** real Stripe SDK wiring + webhooks + order persistence; preview watermarking policy; production SMTP provider selection. These need external credentials and are explicitly out of scope for the first iteration per the spec.

**Placeholder scan:** none — every code step shows complete code.

**Type consistency:** `CodeSender.send(email, code)`, `AuthStore.{put,get,delete}`, `sign/verify` signatures, `CatalogEntry{slug,title,page_count,category}`, `CheckoutSession{reference,amount,currency,status,url}`, and the `_store_*` seam names are consistent across tasks 1–10.
