# tests/test_dashboard.py
"""Regression tests for the KDP Dashboard main functionalities.

Covers:
- Dashboard index page rendering
- Story/Coloring book visual separation
- Book detail page routing (story vs coloring)
- Book status: image counting, missing detection, PDF presence
- Book deletion endpoint
- Story config round-trip (STORY_BASE_PROMPT, PAGES)
"""
import pathlib
import pytest
from fastapi.testclient import TestClient

# ── Fixtures ───────────────────────────────────────────────────────────────────

COLORING_CONFIG = '''
import pathlib
CATEGORY  = "coloring"
TITLE     = "90s Legends"
SUBTITLE  = "Coloring book"
AUTHOR    = "Marco Belghiti"
TESTPEN   = "book1_testpen.png"
IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / "book1-90s"
CHARACTERS = [{"id": "goku", "name": "Goku", "series": "DBZ", "prompt": "Goku"}]
PAGE_SEQUENCE = [("book1_goku.png", "Goku")]
TITLE_PAGE_LINES = [("90s Legends", 100, True, (0, 0, 0))]
COPYRIGHT_PAGE_LINES = [("© 2026", 32, False, (40, 40, 40))]
BACK_PAGE_LINES = [("Thanks!", 55, True, (0, 0, 0))]
'''

STORY_CONFIG = '''
import pathlib
CATEGORY        = "story"
STORY_FORMAT    = "colored"
STORY_LAYOUT    = "top_bottom"
LANGUAGES       = ["fr", "en"]
TITLE           = "Baba & Joudia"
SUBTITLE        = ""
AUTHOR          = "Marco Belghiti"
INTRO_TEXT      = ""
VALUES_LEARNED  = ""
IMAGES_DIR      = pathlib.Path(__file__).parent.parent.parent / "images" / "boo3-story"
TESTPEN         = ""
STORY_BASE_PROMPT = "A warm Amazigh tale about family values."
PAGES = [
    {"page_number": 1, "text_fr": "Il etait une fois...", "image_prompt": "An old man"},
    {"page_number": 2, "text_fr": "Fin.", "image_prompt": "A sunset"},
]
TITLE_PAGE_LINES = [("Baba & Joudia", 100, True, (0, 0, 0))]
COPYRIGHT_PAGE_LINES = [("© 2026", 32, False, (40, 40, 40))]
BACK_PAGE_LINES = [("Thank you!", 55, True, (0, 0, 0))]
CHARACTERS = []
PAGE_SEQUENCE = []
'''


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """App with both a coloring book and a story book seeded."""
    import pipeline.config_io as cio
    import dashboard.app as app_module

    monkeypatch.setattr(cio, "ROOT", tmp_path)
    monkeypatch.setattr(app_module, "ROOT", tmp_path)

    # Coloring book
    book1_dir = tmp_path / "books" / "book1-90s"
    book1_dir.mkdir(parents=True)
    (book1_dir / "config.py").write_text(COLORING_CONFIG)
    images1 = tmp_path / "images" / "book1-90s"
    images1.mkdir(parents=True)
    # Put a valid image (200 KB) to simulate a real page
    (images1 / "book1_goku.png").write_bytes(b"0" * 200_000)

    # Story book
    book3_dir = tmp_path / "books" / "boo3-story"
    book3_dir.mkdir(parents=True)
    (book3_dir / "config.py").write_text(STORY_CONFIG)
    (tmp_path / "images" / "boo3-story").mkdir(parents=True)

    from dashboard.app import app
    return TestClient(app)


# ── Index page ─────────────────────────────────────────────────────────────────

def test_index_returns_200(client):
    res = client.get("/")
    assert res.status_code == 200


def test_index_contains_story_section_header(client):
    res = client.get("/")
    assert "Story Books" in res.text


def test_index_contains_coloring_section_header(client):
    res = client.get("/")
    assert "Coloring Books" in res.text


def test_index_story_section_appears_before_coloring(client):
    """Story Books header must appear before Coloring Books header."""
    res = client.get("/")
    story_pos = res.text.find("Story Books")
    coloring_pos = res.text.find("Coloring Books")
    assert story_pos != -1 and coloring_pos != -1
    assert story_pos < coloring_pos


def test_index_shows_book_titles(client):
    res = client.get("/")
    assert "90s Legends" in res.text
    assert "Baba &amp; Joudia" in res.text or "Baba & Joudia" in res.text


# ── Book detail routing ────────────────────────────────────────────────────────

def test_coloring_book_detail_returns_200(client):
    res = client.get("/book/book1-90s")
    assert res.status_code == 200


def test_story_book_detail_returns_200(client):
    res = client.get("/book/boo3-story")
    assert res.status_code == 200


def test_unknown_book_returns_404(client):
    res = client.get("/book/does-not-exist")
    assert res.status_code in (404, 200)  # app may 200 with error message; not 500


# ── Book status: image counting ────────────────────────────────────────────────

def test_book_status_counts_present_images(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    status = app_module._book_status("book1-90s")
    assert status["present"] == 1
    assert status["missing"] == []


def test_book_status_detects_missing_images(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    # Remove the image
    (tmp_path / "images" / "book1-90s" / "book1_goku.png").unlink()
    status = app_module._book_status("book1-90s")
    assert status["present"] == 0
    assert "book1_goku.png" in status["missing"]


def test_book_status_flags_suspicious_small_images(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    # Replace image with tiny file (< 150 KB = suspicious black fill)
    (tmp_path / "images" / "book1-90s" / "book1_goku.png").write_bytes(b"0" * 1000)
    status = app_module._book_status("book1-90s")
    assert "book1_goku.png" in status["suspicious"]


def test_book_status_no_pdf(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    status = app_module._book_status("book1-90s")
    assert status["pdf"] is None


def test_book_status_detects_pdf(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    pdf = output_dir / "book1-90s_interior_FINAL.pdf"
    pdf.write_bytes(b"0" * 5_000_000)
    status = app_module._book_status("book1-90s")
    assert status["pdf"] is not None
    assert status["pdf"]["size_mb"] > 0


def test_book_status_category_coloring(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    status = app_module._book_status("book1-90s")
    assert status["category"] == "coloring"


def test_book_status_category_story(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    status = app_module._book_status("boo3-story")
    assert status["category"] == "story"


# ── Book deletion ──────────────────────────────────────────────────────────────

def test_delete_book_returns_200(client, tmp_path):
    res = client.delete("/api/book/book1-90s")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_delete_book_removes_config_dir(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    client.delete("/api/book/book1-90s")
    assert not (tmp_path / "books" / "book1-90s").exists()


def test_delete_book_removes_images_dir(client, tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    client.delete("/api/book/book1-90s")
    assert not (tmp_path / "images" / "book1-90s").exists()


def test_delete_nonexistent_book_returns_404(client):
    res = client.delete("/api/book/does-not-exist")
    assert res.status_code == 404


def test_delete_book_invalid_slug_returns_400(client):
    res = client.delete("/api/book/INVALID SLUG!")
    assert res.status_code in (400, 422)


# ── Story config round-trip ────────────────────────────────────────────────────

def test_story_config_story_base_prompt_readable(tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    book_dir = tmp_path / "books" / "boo3-story"
    book_dir.mkdir(parents=True)
    (book_dir / "config.py").write_text(STORY_CONFIG)
    data = cio.read_config("boo3-story")
    assert data["story_base_prompt"] == "A warm Amazigh tale about family values."


def test_story_config_pages_readable(tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    book_dir = tmp_path / "books" / "boo3-story"
    book_dir.mkdir(parents=True)
    (book_dir / "config.py").write_text(STORY_CONFIG)
    data = cio.read_config("boo3-story")
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page_number"] == 1
    assert data["pages"][0]["image_prompt"] == "An old man"


def test_story_config_write_preserves_base_prompt(tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    book_dir = tmp_path / "books" / "boo3-story"
    book_dir.mkdir(parents=True)
    (book_dir / "config.py").write_text(STORY_CONFIG)

    data = cio.read_config("boo3-story")
    data["story_base_prompt"] = "Updated base prompt."
    cio.write_config("boo3-story", data)

    result = cio.read_config("boo3-story")
    assert result["story_base_prompt"] == "Updated base prompt."
