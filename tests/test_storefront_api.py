import datetime as dt
import pathlib
import pytest
from fastapi.testclient import TestClient

import dashboard.app as appmod
from storefront.auth import AuthStore, FakeCodeSender
from storefront.session import sign

ROOT = pathlib.Path(__file__).parent.parent
client = TestClient(appmod.app)

SECRET = "test-secret"


@pytest.fixture
def store_env(tmp_path, monkeypatch):
    client.cookies.clear()
    sender = FakeCodeSender()
    store = AuthStore(tmp_path / "auth.json")
    catalog = {
        "alpha": {"title": "Alpha", "published": True, "pages": [1, 2, 3, 4],
                  "category": "story"},
        "beta": {"title": "Beta", "published": False, "pages": [1, 2],
                 "category": "story"},
    }
    monkeypatch.setattr(appmod, "_store_code_sender", lambda: sender)
    monkeypatch.setattr(appmod, "_store_auth_store", lambda: store)
    monkeypatch.setattr(appmod, "_store_session_secret", lambda: SECRET)
    monkeypatch.setattr(appmod, "_store_catalog_names", lambda: list(catalog))
    monkeypatch.setattr(appmod, "_store_read_config", lambda name: catalog[name])
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {"payment_provider": "stub"})
    return {"sender": sender, "store": store, "catalog": catalog}


def _auth_cookie(email="a@b.com"):
    return sign({"email": email}, SECRET, now=dt.datetime.utcnow())


def test_catalog_lists_only_published(store_env):
    r = client.get("/store")
    assert r.status_code == 200
    assert "Alpha" in r.text
    assert "Beta" not in r.text


def test_personalize_published_ok(store_env):
    r = client.get("/store/alpha")
    assert r.status_code == 200
    assert "Alpha" in r.text


def test_personalize_unpublished_404(store_env):
    r = client.get("/store/beta")
    assert r.status_code == 404


def test_auth_request_then_verify_sets_cookie(store_env):
    r = client.post("/store/auth/request", json={"email": "a@b.com"})
    assert r.status_code == 200
    assert store_env["sender"].sent[0][0] == "a@b.com"
    code = store_env["sender"].sent[0][1]
    r2 = client.post("/store/auth/verify", json={"email": "a@b.com", "code": code})
    assert r2.status_code == 200
    assert "sf_session" in r2.cookies


def test_auth_verify_wrong_code_401(store_env):
    client.post("/store/auth/request", json={"email": "a@b.com"})
    r = client.post("/store/auth/verify", json={"email": "a@b.com", "code": "000000"})
    assert r.status_code == 401


def test_checkout_requires_session(store_env):
    r = client.post("/store/alpha/checkout")
    assert r.status_code == 401


def test_checkout_with_session_returns_pending(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_load_pricing_settings", lambda: {
        "currency": "USD", "bw_per_page": 0.012, "color_per_page": 0.07,
        "paper_quality": {"standard": 1.0, "premium": 1.5},
        "cover_cost": 1.0, "markup_multiplier": 2.5,
    })
    r = client.post("/store/alpha/checkout", cookies={"sf_session": _auth_cookie()})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["currency"] == "USD"
    assert data["amount"] > 0
    assert data["reference"].startswith("alpha-")


def test_publish_toggle(monkeypatch):
    saved = {}
    monkeypatch.setattr(appmod, "read_config", lambda name: {"title": "X", "pages": []})
    monkeypatch.setattr(appmod, "write_config", lambda name, cfg: saved.update(cfg))
    r = client.post("/api/storyforge/alpha/publish?published=true")
    assert r.status_code == 200
    assert r.json()["published"] is True
    assert saved["published"] is True
