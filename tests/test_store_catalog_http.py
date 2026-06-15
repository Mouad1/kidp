import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def catalog_client(tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    monkeypatch.setattr(app_module, "_store_catalog_names", lambda: ["alpha", "beta"])

    def fake_config(name):
        return {
            "alpha": {
                "title": "Alpha",
                "published": True,
                "pages": [{}, {}, {}],
                "languages": ["fr", "en"],
                "intro_text": "A great story.",
            },
            "beta": {
                "title": "Beta",
                "published": True,
                "pages": [{}, {}],
                "languages": ["fr"],
                "intro_text": "Une belle histoire.",
            },
        }[name]

    monkeypatch.setattr(app_module, "_store_read_config", fake_config)
    return TestClient(app_module.app)


def test_catalog_lists_books_for_default_language(catalog_client):
    r = catalog_client.get("/store")
    assert r.status_code == 200
    assert "Alpha" in r.text
    assert "Beta" in r.text


def test_catalog_shows_all_books_regardless_of_language(catalog_client):
    r = catalog_client.get("/store?lang=en")
    assert r.status_code == 200
    assert "Alpha" in r.text
    assert "Beta" in r.text


def test_catalog_shows_language_count_badge(catalog_client):
    r = catalog_client.get("/store")
    assert r.status_code == 200
    assert "4 langues" in r.text


def test_catalog_language_selector_is_present(catalog_client):
    r = catalog_client.get("/store")
    assert r.status_code == 200
    assert 'name="lang"' in r.text
    assert 'value="fr"' in r.text
    assert 'value="en"' in r.text


def test_catalog_empty_state_when_no_stories_available(tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    monkeypatch.setattr(app_module, "_store_catalog_names", lambda: [])
    client = TestClient(app_module.app)
    r = client.get("/store?lang=es")
    assert r.status_code == 200
    assert "No hay cuentos disponibles" in r.text


def test_language_cookie_has_root_path(catalog_client):
    r = catalog_client.post("/store/lang", data={"lang": "es", "next": "/store"}, follow_redirects=False)
    assert r.status_code == 303
    cookie = r.headers.get("set-cookie", "")
    assert "sf_lang=es" in cookie
    assert "Path=/" in cookie
