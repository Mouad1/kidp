import pathlib
import pytest
from fastapi.testclient import TestClient

FAKE_CONFIG = '''
import pathlib
TITLE    = "Test Book"
SUBTITLE = "Sub"
AUTHOR   = "Marco Belghiti"
TESTPEN  = "tp.png"
IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / "book-test"
CHARACTERS = [{"id": "hero", "name": "The Hero", "series": "S1", "prompt": "a hero"}]
PAGE_SEQUENCE = [("book_test_hero.png", "The Hero")]
TITLE_PAGE_LINES = [("Test Book", 120, True, (0, 0, 0))]
COPYRIGHT_PAGE_LINES = [("© 2026", 32, True, (40, 40, 40))]
BACK_PAGE_LINES = [("Thanks!", 55, True, (0, 0, 0))]
'''


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Patch ROOT dans config_io et app
    import pipeline.config_io as cio
    import dashboard.app as app_module
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    monkeypatch.setattr(app_module, "ROOT", tmp_path)

    # Créer le faux livre
    book_dir = tmp_path / "books" / "book-test"
    book_dir.mkdir(parents=True)
    (book_dir / "config.py").write_text(FAKE_CONFIG)
    (tmp_path / "images" / "book-test").mkdir(parents=True)

    from dashboard.app import app
    return TestClient(app)


def test_get_config(client):
    res = client.get("/api/book/book-test/config")
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Test Book"
    assert data["author"] == "Marco Belghiti"
    assert len(data["characters"]) == 1


def test_get_config_not_found(client):
    res = client.get("/api/book/nonexistent/config")
    assert res.status_code == 404


def test_put_config(client):
    payload = {
        "title": "Updated Title",
        "subtitle": "Updated Sub",
        "author": "Marco Belghiti",
        "testpen": "tp.png",
        "images_folder": "book-test",
        "characters": [{"id": "hero", "name": "The Hero", "series": "S1", "prompt": "prompt"}],
        "page_sequence": [{"file": "book_test_hero.png", "label": "The Hero"}],
    }
    res = client.put("/api/book/book-test/config", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Vérifier que le fichier a été mis à jour
    verify = client.get("/api/book/book-test/config")
    assert verify.json()["title"] == "Updated Title"


def test_post_new_book(client, tmp_path):
    payload = {
        "slug": "book3-test",
        "title": "New Book",
        "subtitle": "A new book",
        "author": "Marco Belghiti",
        "characters": [],
    }
    res = client.post("/api/books/new", json=payload)
    assert res.status_code == 200
    assert res.json()["slug"] == "book3-test"
    assert (tmp_path / "books" / "book3-test" / "config.py").exists()
    assert (tmp_path / "images" / "book3-test").exists()


def test_post_new_book_invalid_slug(client):
    payload = {"slug": "INVALID SLUG!", "title": "T", "subtitle": "S", "author": "A", "characters": []}
    res = client.post("/api/books/new", json=payload)
    assert res.status_code == 400


def test_post_new_book_duplicate(client):
    payload = {"slug": "book-test", "title": "T", "subtitle": "S", "author": "A", "characters": []}
    res = client.post("/api/books/new", json=payload)
    assert res.status_code == 409


def test_put_config_not_found(client):
    payload = {
        "title": "T", "subtitle": "S", "author": "A",
        "testpen": "", "images_folder": "", "characters": [], "page_sequence": []
    }
    res = client.put("/api/book/nonexistent/config", json=payload)
    assert res.status_code == 404
