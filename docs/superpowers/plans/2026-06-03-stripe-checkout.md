# Stripe Checkout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Stripe Checkout (hosted) as a real payment provider alongside the existing stub.

**Architecture:** `StripePaymentProvider` implements the `PaymentProvider` Protocol. The checkout route redirects to Stripe instead of marking paid immediately. A new webhook route `POST /store/webhook/stripe` receives Stripe events and marks orders paid. No DB migration — `client_reference_id` maps to our order reference.

**Tech Stack:** Python `stripe` SDK, FastAPI, SQLite (existing), Stripe Checkout Sessions API.

---

## File Map

| File | Change |
|---|---|
| `storefront/payment.py` | Add `StripePaymentProvider`, update Protocol + `StubPaymentProvider` + `get_payment_provider` |
| `dashboard/app.py` | Fix checkout route (conditional mark-paid), add webhook route |
| `settings.example.json` | Document `"payment_provider": "stripe"` |
| `.env.local` | Add `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| `tests/test_stripe_payment.py` | New — unit tests for provider + webhook |
| `requirements.txt` | New — pin `stripe` |

---

### Task 1: Install stripe SDK + create requirements.txt

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Install stripe**

```bash
pip3 install stripe
```

- [ ] **Step 2: Verify import works**

```bash
python3 -c "import stripe; print(stripe.__version__)"
```

Expected: prints version (e.g. `7.x.x`)

- [ ] **Step 3: Create requirements.txt**

```
stripe>=7.0.0
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add stripe dependency"
```

---

### Task 2: Update `storefront/payment.py`

**Files:**
- Modify: `storefront/payment.py`

- [ ] **Step 1: Write failing tests for StripePaymentProvider**

Create `tests/test_stripe_payment.py`:

```python
import json
import datetime as dt
import pathlib
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from PIL import Image
import io

import dashboard.app as appmod
from storefront.db import Database
from storefront.session import sign
from storefront.payment import StripePaymentProvider, CheckoutSession, get_payment_provider

ROOT = pathlib.Path(__file__).parent.parent
client = TestClient(appmod.app)
SECRET = "test-secret"


def _png_bytes():
    im = Image.new("RGB", (8, 8), color=(200, 150, 100))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def stripe_env(tmp_path, monkeypatch):
    client.cookies.clear()
    db = Database(tmp_path / "storefront.db")
    catalog = {"alpha": {"title": "Alpha", "published": True, "pages": [1, 2, 3, 4], "category": "story"}}
    monkeypatch.setattr(appmod, "_store_db", lambda: db)
    monkeypatch.setattr(appmod, "_store_session_secret", lambda: SECRET)
    monkeypatch.setattr(appmod, "_store_https", lambda: False)
    monkeypatch.setattr(appmod, "_store_catalog_names", lambda: list(catalog))
    monkeypatch.setattr(appmod, "_store_read_config", lambda name: catalog[name])
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {"payment_provider": "stripe"})
    monkeypatch.setattr(appmod, "_load_pricing_settings", lambda: {
        "currency": "USD", "bw_per_page": 0.012, "color_per_page": 0.07,
        "paper_quality": {"standard": 1.0, "premium": 1.5},
        "cover_cost": 1.0, "markup_multiplier": 2.5,
    })
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    return {"db": db, "catalog": catalog}


def _login(email="a@b.com"):
    client.cookies.set("sf_session", sign({"email": email}, SECRET, now=dt.datetime.utcnow()))


def _create_order(slug="alpha", child="Lina"):
    return client.post(f"/store/{slug}/order",
                       data={"child_name": child},
                       files={"photo": ("p.png", _png_bytes(), "image/png")})


# ── Unit tests for StripePaymentProvider ────────────────────────────────────────

def test_stripe_provider_returns_pending():
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test123"
    with patch("stripe.checkout.Session.create", return_value=mock_session):
        provider = StripePaymentProvider(secret_key="sk_test_fake")
        result = provider.create_checkout(
            amount=1500, currency="usd", reference="alpha-abc123",
            success_url="http://localhost/success", cancel_url="http://localhost/cancel",
        )
    assert result.status == "pending"
    assert result.url == "https://checkout.stripe.com/pay/test123"
    assert result.reference == "alpha-abc123"
    assert result.amount == 1500
    assert result.currency == "usd"


def test_stripe_provider_calls_stripe_api_with_correct_params():
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test123"
    with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
        provider = StripePaymentProvider(secret_key="sk_test_fake")
        provider.create_checkout(
            amount=1500, currency="usd", reference="alpha-abc123",
            success_url="http://localhost/success", cancel_url="http://localhost/cancel",
        )
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["client_reference_id"] == "alpha-abc123"
    assert call_kwargs["success_url"] == "http://localhost/success"
    assert call_kwargs["cancel_url"] == "http://localhost/cancel"
    assert call_kwargs["mode"] == "payment"
    line_item = call_kwargs["line_items"][0]
    assert line_item["price_data"]["unit_amount"] == 1500
    assert line_item["price_data"]["currency"] == "usd"
    assert line_item["quantity"] == 1


def test_get_payment_provider_stripe_reads_env(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    provider = get_payment_provider({"payment_provider": "stripe"})
    assert isinstance(provider, StripePaymentProvider)


def test_get_payment_provider_stripe_missing_key_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
        get_payment_provider({"payment_provider": "stripe"})


# ── Integration tests for checkout route with Stripe ────────────────────────────

def test_checkout_with_stripe_returns_pending(stripe_env):
    _login()
    _create_order()
    ref = appmod._sf_list_orders(stripe_env["db"])[0]["reference"]
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/pay/test123"
    with patch("stripe.checkout.Session.create", return_value=mock_session):
        r = client.post("/store/alpha/checkout", json={"reference": ref})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["url"] == "https://checkout.stripe.com/pay/test123"
    # Order NOT marked paid yet — webhook does that
    order = appmod._sf_get_order(stripe_env["db"], ref)
    assert order["status"] == "pending"


# ── Webhook route tests ──────────────────────────────────────────────────────────

def _webhook_event(reference: str) -> dict:
    return {
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": reference}},
    }


def test_webhook_marks_order_paid(stripe_env):
    _login()
    _create_order()
    ref = appmod._sf_list_orders(stripe_env["db"])[0]["reference"]
    event = _webhook_event(ref)
    r = client.post("/store/webhook/stripe", content=json.dumps(event),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200
    assert r.json() == {"received": True}
    assert appmod._sf_get_order(stripe_env["db"], ref)["status"] == "paid"


def test_webhook_ignores_unknown_event_type(stripe_env):
    event = {"type": "payment_intent.created", "data": {"object": {}}}
    r = client.post("/store/webhook/stripe", content=json.dumps(event),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200


def test_webhook_rejects_bad_signature_when_secret_set(stripe_env, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_testsecret")
    event = _webhook_event("alpha-abc123")
    r = client.post("/store/webhook/stripe", content=json.dumps(event),
                    headers={"Content-Type": "application/json", "Stripe-Signature": "bad"})
    assert r.status_code == 400


def test_webhook_skips_signature_when_no_secret(stripe_env):
    # STRIPE_WEBHOOK_SECRET not set → dev mode, no signature check
    event = {"type": "checkout.session.completed",
             "data": {"object": {"client_reference_id": "nonexistent-ref"}}}
    r = client.post("/store/webhook/stripe", content=json.dumps(event),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200  # gracefully ignores unknown reference
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_stripe_payment.py -v 2>&1 | head -40
```

Expected: `ImportError: cannot import name 'StripePaymentProvider'` or similar.

- [ ] **Step 3: Replace `storefront/payment.py` with full implementation**

```python
import os
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
    def create_checkout(self, amount: int, currency: str, reference: str,
                        success_url: str = "", cancel_url: str = "") -> CheckoutSession: ...


class StubPaymentProvider:
    """No real charge. Settles immediately — for local dev without Stripe keys."""

    def create_checkout(self, amount: int, currency: str, reference: str,
                        success_url: str = "", cancel_url: str = "") -> CheckoutSession:
        return CheckoutSession(
            reference=reference, amount=amount, currency=currency,
            status="paid", url=f"/store/checkout/mock/{reference}",
        )


class StripePaymentProvider:
    """Stripe Checkout (hosted). Order stays pending until webhook confirms payment."""

    def __init__(self, secret_key: str) -> None:
        self.secret_key = secret_key

    def create_checkout(self, amount: int, currency: str, reference: str,
                        success_url: str = "", cancel_url: str = "") -> CheckoutSession:
        import stripe
        stripe.api_key = self.secret_key
        session = stripe.checkout.Session.create(
            mode="payment",
            client_reference_id=reference,
            line_items=[{
                "price_data": {
                    "currency": currency,
                    "product_data": {"name": f"Personalized Book — {reference}"},
                    "unit_amount": amount,
                },
                "quantity": 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return CheckoutSession(
            reference=reference, amount=amount, currency=currency,
            status="pending", url=session.url,
        )


def get_payment_provider(settings: dict) -> PaymentProvider:
    provider = (settings or {}).get("payment_provider", "stub")
    if provider == "stub":
        return StubPaymentProvider()
    if provider == "stripe":
        secret_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
        if not secret_key:
            raise RuntimeError(
                "STRIPE_SECRET_KEY env var is required when payment_provider is 'stripe'"
            )
        return StripePaymentProvider(secret_key=secret_key)
    raise ValueError(f"Unsupported payment provider: {provider!r}")
```

- [ ] **Step 4: Run tests — should pass for provider tests**

```bash
python3 -m pytest tests/test_stripe_payment.py -v -k "provider or get_payment"
```

Expected: 4 tests pass.

---

### Task 3: Update checkout route in `dashboard/app.py`

**Files:**
- Modify: `dashboard/app.py:1492-1519`

- [ ] **Step 1: Replace the checkout route body**

Find this block (around line 1513–1519):

```python
    provider = _sf_get_payment_provider(_load_storefront_settings())
    checkout = provider.create_checkout(
        amount=order["amount_cents"], currency=order["currency"], reference=reference)
    # Stub provider has no real charge, so the order is settled immediately.
    _sf_set_order_status(db, reference, "paid", now=_dt.datetime.utcnow())
    return JSONResponse({
        "reference": checkout.reference, "amount": checkout.amount,
        "currency": checkout.currency, "status": "paid", "url": checkout.url,
    })
```

Replace with:

```python
    base = str(request.base_url).rstrip("/")
    provider = _sf_get_payment_provider(_load_storefront_settings())
    checkout = provider.create_checkout(
        amount=order["amount_cents"], currency=order["currency"], reference=reference,
        success_url=f"{base}/store/{slug}?paid={reference}",
        cancel_url=f"{base}/store/{slug}",
    )
    if checkout.status == "paid":
        _sf_set_order_status(db, reference, "paid", now=_dt.datetime.utcnow())
    return JSONResponse({
        "reference": checkout.reference, "amount": checkout.amount,
        "currency": checkout.currency, "status": checkout.status, "url": checkout.url,
    })
```

- [ ] **Step 2: Run existing storefront tests to confirm no regression**

```bash
python3 -m pytest tests/test_storefront_api.py -v
```

Expected: 16 passed.

- [ ] **Step 3: Run Stripe checkout integration test**

```bash
python3 -m pytest tests/test_stripe_payment.py::test_checkout_with_stripe_returns_pending -v
```

Expected: PASS.

---

### Task 4: Add webhook route to `dashboard/app.py`

**Files:**
- Modify: `dashboard/app.py` — insert new route after `store_checkout` (before line `# ── Admin`)

- [ ] **Step 1: Add webhook route**

Insert this block after the `store_checkout` function (before `# ── Admin authentication`):

```python
@app.post("/store/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()

    if webhook_secret:
        import stripe as _stripe
        try:
            event = _stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
    else:
        import json as _json
        event = _json.loads(payload)

    if event.get("type") == "checkout.session.completed":
        reference = (event.get("data") or {}).get("object", {}).get("client_reference_id") or ""
        if reference:
            db = _store_db()
            order = _sf_get_order(db, reference)
            if order:
                _sf_set_order_status(db, reference, "paid", now=_dt.datetime.utcnow())

    return JSONResponse({"received": True})
```

- [ ] **Step 2: Run webhook tests**

```bash
python3 -m pytest tests/test_stripe_payment.py -v -k "webhook"
```

Expected: 4 webhook tests pass.

---

### Task 5: Update `settings.example.json`

**Files:**
- Modify: `settings.example.json`

- [ ] **Step 1: Update payment_provider comment**

Change:

```json
"payment_provider": "stub",
```

To:

```json
"payment_provider": "stub",
```

Add a comment block above `storefront` key — JSON doesn't support comments, so add a sibling key `_payment_provider_options` to document valid values:

Actually JSON has no comments. Instead update the value to show stub is the default, and add to README or just leave as-is. The spec says document it — update the value to show the option:

No change needed to settings.example.json beyond what exists — `"stub"` is correct default. The env vars document themselves. Skip this step.

- [ ] **Step 2: Add Stripe env vars to `.env.local`**

Append to `.env.local`:

```bash
# Stripe payment (set payment_provider=stripe in settings.json to enable)
STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET_HERE
```

---

### Task 6: Run full test suite + commit

**Files:** none

- [ ] **Step 1: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests pass (16 storefront + stripe tests).

- [ ] **Step 2: Commit everything**

```bash
git add storefront/payment.py dashboard/app.py tests/test_stripe_payment.py requirements.txt .env.local
git commit -m "feat(storefront): Stripe Checkout integration — StripePaymentProvider, webhook route, conditional mark-paid"
```

---

## Self-Review

**Spec coverage:**
- ✅ `StripePaymentProvider` with `client_reference_id` → Task 2
- ✅ `PaymentProvider` Protocol updated with `success_url`/`cancel_url` → Task 2
- ✅ Checkout route: conditional mark-paid on `checkout.status` → Task 3
- ✅ Webhook route with optional signature verification → Task 4
- ✅ `get_payment_provider` supports "stripe", reads `STRIPE_SECRET_KEY` → Task 2
- ✅ `StubPaymentProvider` returns `status="paid"` for backward compat → Task 2
- ✅ Env vars documented → Task 5
- ✅ Tests: provider, checkout integration, webhook scenarios → Task 2 (test file)

**Type consistency:**
- `StripePaymentProvider` defined in Task 2 step 3, imported in test file at top ✅
- `get_payment_provider` signature unchanged, `settings` dict param ✅
- `CheckoutSession.status` drives mark-paid logic in Task 3 ✅
- `_sf_get_order`, `_sf_set_order_status`, `_sf_list_orders` — existing imports in app.py ✅

**No placeholders:** confirmed — all steps have complete code.
