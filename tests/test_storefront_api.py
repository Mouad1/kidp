import datetime as dt
import io
import pathlib
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import dashboard.app as appmod
from storefront.auth import FakeCodeSender, SqliteAuthStore
from storefront.db import Database
from storefront.session import sign

ROOT = pathlib.Path(__file__).parent.parent
client = TestClient(appmod.app)

SECRET = "test-secret"


def _png_bytes():
    im = Image.new("RGB", (8, 8), color=(200, 150, 100))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def store_env(tmp_path, monkeypatch):
    client.cookies.clear()
    sender = FakeCodeSender()
    db = Database(tmp_path / "storefront.db")
    store = SqliteAuthStore(db)
    catalog = {
        "alpha": {"title": "Alpha", "published": True, "pages": [1, 2, 3, 4],
                  "category": "story"},
        "beta": {"title": "Beta", "published": False, "pages": [1, 2],
                 "category": "story"},
    }
    monkeypatch.setattr(appmod, "_store_code_sender", lambda: sender)
    monkeypatch.setattr(appmod, "_store_auth_store", lambda: store)
    monkeypatch.setattr(appmod, "_store_db", lambda: db)
    monkeypatch.setattr(appmod, "_store_session_secret", lambda: SECRET)
    monkeypatch.setattr(appmod, "_store_https", lambda: False)
    monkeypatch.setattr(appmod, "_store_catalog_names", lambda: list(catalog))
    monkeypatch.setattr(appmod, "_store_read_config", lambda name: catalog[name])
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {"payment_provider": "stub"})
    monkeypatch.setattr(appmod, "_load_pricing_settings", lambda: {
        "currency": "USD", "bw_per_page": 0.012, "color_per_page": 0.07,
        "paper_quality": {"standard": 1.0, "premium": 1.5},
        "cover_cost": 1.0, "markup_multiplier": 2.5,
    })
    return {"sender": sender, "store": store, "db": db, "catalog": catalog}


def _auth_cookie(email="a@b.com"):
    return sign({"email": email}, SECRET, now=dt.datetime.utcnow())


def _login(email="a@b.com"):
    client.cookies.set("sf_session", _auth_cookie(email))


def _create_order(slug="alpha", child="Lina"):
    return client.post(f"/store/{slug}/order",
                       data={"child_name": child},
                       files={"photo": ("p.png", _png_bytes(), "image/png")})


def test_catalog_lists_only_published(store_env):
    r = client.get("/store")
    assert r.status_code == 200
    assert "Alpha" in r.text
    assert "Beta" not in r.text
    # Price is shown on the catalog grid (4 pages: 1.0 + 4*0.07*1.0 = 1.28 * 2.5 = 3.20)
    assert "$3.20" in r.text


def test_catalog_shows_intro_text(store_env):
    catalog = store_env["catalog"]
    catalog["alpha"]["intro_text"] = {"fr": "Une histoire magique.", "en": "A magical story."}
    r = client.get("/store", headers={"Accept-Language": "fr"})
    assert r.status_code == 200
    assert "Une histoire magique." in r.text


def test_personalize_published_ok(store_env):
    r = client.get("/store/alpha")
    assert r.status_code == 200
    assert "Alpha" in r.text
    # Price is shown on the product page
    assert "$3.20" in r.text


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
    r = client.post("/store/alpha/checkout", json={"reference": "x"})
    assert r.status_code == 401


def test_order_requires_session(store_env):
    r = _create_order()
    assert r.status_code == 401


def test_order_creation_returns_pending(store_env):
    _login()
    r = _create_order(child="Lina")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "pending"
    assert data["currency"] == "USD"
    assert data["amount"] > 0
    assert data["reference"].startswith("alpha-")
    order = appmod._sf_get_order(store_env["db"], data["reference"])
    assert order["child_name"] == "Lina"
    assert order["email"] == "a@b.com"


def test_checkout_marks_order_paid(store_env):
    _login()
    ref = _create_order().json()["reference"]
    r = client.post("/store/alpha/checkout", json={"reference": ref})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "paid"
    assert appmod._sf_get_order(store_env["db"], ref)["status"] == "paid"


def test_checkout_rejects_other_users_order(store_env):
    _login("a@b.com")
    ref = _create_order().json()["reference"]
    client.cookies.clear()
    client.cookies.set("sf_session", _auth_cookie("other@b.com"))
    r = client.post("/store/alpha/checkout", json={"reference": ref})
    assert r.status_code == 403


def test_admin_orders_lists_paid(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: {"email": "admin", "admin": True})
    _login()
    _create_order(child="Lina")
    r = client.get("/admin/orders")
    assert r.status_code == 200
    assert "Lina" in r.text


def test_admin_stats_returns_kpis(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: {"email": "admin", "admin": True})
    r = client.get("/api/admin/stats")
    assert r.status_code == 200
    body = r.json()
    assert "revenue_today_cents" in body
    assert "revenue_month_cents" in body
    assert "pending_count" in body


def test_admin_stats_requires_admin(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: None)
    r = client.get("/api/admin/stats")
    assert r.status_code == 401



def test_admin_auth_request_returns_503_without_smtp(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_sf_is_admin", lambda db, email: True)

    r = client.post("/admin/auth/request", json={"email": "admin@example.com"})

    assert r.status_code == 503
    assert "Email delivery is not configured" in r.json()["detail"]


def test_admin_auth_request_succeeds_with_smtp_sender(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_sf_is_admin", lambda db, email: True)

    class _Sender:
        def __init__(self):
            self.sent = []

        def send(self, email, code):
            self.sent.append((email, code))

    smtp_like_sender = _Sender()
    monkeypatch.setattr(appmod, "_store_code_sender", lambda: smtp_like_sender)

    r = client.post("/admin/auth/request", json={"email": "admin@example.com"})

    assert r.status_code == 200
    assert r.json()["sent"] is True
    assert smtp_like_sender.sent


def test_store_auth_request_returns_502_when_sender_fails(store_env, monkeypatch):
    class _FailingSender:
        def send(self, email, code):
            raise RuntimeError("boom")

    monkeypatch.setattr(appmod, "_store_code_sender", lambda: _FailingSender())
    r = client.post("/store/auth/request", json={"email": "user@example.com"})
    assert r.status_code == 502
    assert "Failed to send email code" in r.json()["detail"]


def test_admin_auth_request_returns_502_when_sender_fails(store_env, monkeypatch):
    class _FailingSender:
        def send(self, email, code):
            raise RuntimeError("boom")

    monkeypatch.setattr(appmod, "_sf_is_admin", lambda db, email: True)
    monkeypatch.setattr(appmod, "_store_code_sender", lambda: _FailingSender())
    r = client.post("/admin/auth/request", json={"email": "admin@example.com"})
    assert r.status_code == 502
    assert "Failed to send email code" in r.json()["detail"]


def test_publish_toggle(monkeypatch):
    saved = {}
    monkeypatch.setattr(appmod, "read_config", lambda name: {"title": "X", "pages": []})
    monkeypatch.setattr(appmod, "write_config", lambda name, cfg: saved.update(cfg))
    r = client.post("/api/storyforge/alpha/publish?published=true")
    assert r.status_code == 200
    assert r.json()["published"] is True
    assert saved["published"] is True


# ── Face-swap preview endpoint tests ─────────────────────────────────────────

from storyforge.imagegen import FakeImageGenerator
from storyforge.types import Template, PageBeat


def _fake_template() -> Template:
    return Template(
        name="alpha",
        slug="alpha",
        mode="color",
        language_default="fr",
        art_style="watercolor",
        variables=[],
        pages=[
            PageBeat(beat="intro", text="Hello {HERO_NAME}!", image_prompt="A hero in {HERO}"),
        ],
    )


@pytest.fixture
def preview_env(store_env, monkeypatch):
    """Extend store_env with fake storyforge dependencies for preview endpoint."""
    fake_gen = FakeImageGenerator()
    monkeypatch.setattr(appmod, "_backend_provider", lambda: fake_gen)
    monkeypatch.setattr(appmod, "_analyze_provider", lambda photos: "curly hair, big eyes")
    monkeypatch.setattr(appmod, "_sf_load_template", lambda slug: _fake_template())
    return {"gen": fake_gen}


def test_preview_returns_cover_and_page1(preview_env):
    r = client.post(
        "/store/alpha/preview",
        data={"child_name": "Lina"},
        files={"photo": ("p.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["cover"].startswith("data:image/png;base64,")
    assert data["page1"].startswith("data:image/png;base64,")
    assert data["page_count"] == 1  # template has 1 page


def test_preview_exactly_3_image_calls(preview_env):
    """Strict cap: portrait + page1 + cover = 3 Gemini image calls."""
    client.post(
        "/store/alpha/preview",
        data={"child_name": "Lina"},
        files={"photo": ("p.png", _png_bytes(), "image/png")},
    )
    assert len(preview_env["gen"].calls) == 3


def test_preview_requires_child_name(preview_env):
    r = client.post(
        "/store/alpha/preview",
        data={"child_name": "   "},
        files={"photo": ("p.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 400


def test_preview_requires_photo(preview_env):
    r = client.post(
        "/store/alpha/preview",
        data={"child_name": "Lina"},
        files={"photo": ("p.png", b"", "image/png")},
    )
    assert r.status_code == 400


def test_preview_unpublished_404(preview_env):
    r = client.post(
        "/store/beta/preview",
        data={"child_name": "Lina"},
        files={"photo": ("p.png", _png_bytes(), "image/png")},
    )
    assert r.status_code == 404


def test_admin_list_emails_returns_list(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: {"email": "admin", "admin": True})
    from storefront.admin import seed_admins
    import datetime as dt
    seed_admins(store_env["db"], ["test@example.com"], now=dt.datetime.utcnow())
    r = client.get("/api/admin/emails")
    assert r.status_code == 200
    emails = [e["email"] for e in r.json()["emails"]]
    assert "test@example.com" in emails


def test_admin_add_email(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: {"email": "admin", "admin": True})
    r = client.post("/api/admin/emails", json={"email": "new@example.com"})
    assert r.status_code == 200
    assert r.json()["added"] is True
    assert appmod._sf_is_admin(store_env["db"], "new@example.com")


def test_admin_remove_email(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: {"email": "admin", "admin": True})
    from storefront.admin import seed_admins
    import datetime as dt
    # Seed two admins so last-admin guard doesn't block the delete
    seed_admins(store_env["db"], ["keeper@example.com", "todelete@example.com"], now=dt.datetime.utcnow())
    r = client.delete("/api/admin/emails/todelete@example.com")
    assert r.status_code == 200
    assert not appmod._sf_is_admin(store_env["db"], "todelete@example.com")


def test_admin_email_endpoints_require_auth(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: None)
    assert client.get("/api/admin/emails").status_code == 401
    assert client.post("/api/admin/emails", json={"email": "x@y.com"}).status_code == 401
    assert client.delete("/api/admin/emails/x@y.com").status_code == 401

