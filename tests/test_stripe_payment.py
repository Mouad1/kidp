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
    event = {"type": "checkout.session.completed",
             "data": {"object": {"client_reference_id": "nonexistent-ref"}}}
    r = client.post("/store/webhook/stripe", content=json.dumps(event),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 200
