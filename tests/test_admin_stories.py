# tests/test_admin_stories.py
import pathlib
import pytest
from fastapi.testclient import TestClient

import dashboard.app as appmod

ROOT = pathlib.Path(__file__).parent.parent
client = TestClient(appmod.app)

SECRET = "test-secret"

BOOKS = {
    "lolo-hero":    {"title": "Lolo Hero",     "category": "story",    "in_sequence": 22, "published": True},
    "joudia-world": {"title": "Joudia's World", "category": "storyforge","in_sequence": 18, "published": False},
}


@pytest.fixture
def stories_env(tmp_path, monkeypatch):
    from storefront.db import Database
    db = Database(tmp_path / "storefront.db")
    monkeypatch.setattr(appmod, "_store_db", lambda: db)
    monkeypatch.setattr(appmod, "_store_session_secret", lambda: SECRET)
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {})
    monkeypatch.setattr(appmod, "_list_books", lambda: list(BOOKS))
    monkeypatch.setattr(appmod, "_book_status", lambda name: {"name": name, **BOOKS[name]})
    client.cookies.clear()
    return db


def _admin_cookie():
    from storefront.session import sign
    import datetime as dt
    return sign({"email": "admin@test.com", "admin": True}, SECRET, now=dt.datetime.utcnow())


def _login_admin():
    client.cookies.set("sf_admin", _admin_cookie())


def test_admin_stories_redirects_without_session(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_admin_enabled", lambda: True)
    r = client.get("/admin/stories", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


def test_admin_stories_returns_200_with_valid_session(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    r = client.get("/admin/stories")
    assert r.status_code == 200


def test_admin_stories_lists_all_book_slugs(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    r = client.get("/admin/stories")
    assert "lolo-hero" in r.text
    assert "joudia-world" in r.text


def test_admin_stories_published_shows_depublier(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    r = client.get("/admin/stories")
    assert "Dépublier" in r.text


def test_admin_stories_unpublished_shows_publier(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    r = client.get("/admin/stories")
    assert "Publier" in r.text


def test_admin_stories_shows_order_counts(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    # Insert one order for lolo-hero
    from storefront.db import create_order
    import datetime as dt
    create_order(stories_env, reference="lolo-hero-abc123", slug="lolo-hero",
                 email="a@b.com", child_name="Lina", photo_path="/tmp/p.png",
                 page_count=22, amount_cents=1200, currency="USD",
                 now=dt.datetime.utcnow())
    r = client.get("/admin/stories")
    assert "1" in r.text  # 1 commande for lolo-hero
