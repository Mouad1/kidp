# tests/test_config_io.py
import pathlib
import pytest
from pipeline.config_io import read_config, write_config

FAKE_CONFIG = '''
import pathlib
TITLE    = "Test Book"
SUBTITLE = "A subtitle"
AUTHOR   = "Marco Belghiti"
TESTPEN  = "book_test_testpen.png"
IMAGES_DIR = pathlib.Path(__file__).parent.parent.parent / "images" / "book-test"
CHARACTERS = [{"id": "hero", "name": "The Hero", "series": "S1", "prompt": "a hero"}]
PAGE_SEQUENCE = [("book_test_hero.png", "The Hero")]
TITLE_PAGE_LINES = [("Test Book", 120, True, (0, 0, 0))]
COPYRIGHT_PAGE_LINES = [("© 2026", 32, True, (40, 40, 40))]
BACK_PAGE_LINES = [("Thank you!", 55, True, (0, 0, 0))]
'''


@pytest.fixture()
def fake_book(tmp_path, monkeypatch):
    """Crée un faux livre dans tmp_path et patche ROOT."""
    book_dir = tmp_path / "books" / "book-test"
    book_dir.mkdir(parents=True)
    (book_dir / "config.py").write_text(FAKE_CONFIG)
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    return tmp_path


def test_read_config_returns_dict(fake_book):
    data = read_config("book-test")
    assert data["title"] == "Test Book"
    assert data["author"] == "Marco Belghiti"
    assert data["images_folder"] == "book-test"
    assert data["characters"] == [{"id": "hero", "name": "The Hero", "series": "S1", "prompt": "a hero"}]
    assert data["page_sequence"] == [{"file": "book_test_hero.png", "label": "The Hero"}]
    assert data["title_page_lines"] == [["Test Book", 120, True, [0, 0, 0]]]


def test_read_config_defaults_published_false(fake_book):
    data = read_config("book-test")
    assert data["published"] is False


def test_write_config_roundtrips_published(fake_book, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", fake_book)
    data = read_config("book-test")
    data["published"] = True
    write_config("book-test", data)
    assert read_config("book-test")["published"] is True


def test_read_config_missing_book(tmp_path, monkeypatch):
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError):
        read_config("nonexistent")


def test_write_config_creates_valid_python(fake_book, monkeypatch):
    """write_config doit générer un config.py importable par le pipeline."""
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", fake_book)

    data = {
        "title": "New Title",
        "subtitle": "New Subtitle",
        "author": "Marco Belghiti",
        "testpen": "book-test_testpen.png",
        "images_folder": "book-test",
        "characters": [
            {"id": "hero", "name": "The Hero", "series": "S1", "prompt": "a hero prompt"},
        ],
        "page_sequence": [
            {"file": "book-test_hero.png", "label": "The Hero"},
        ],
    }
    write_config("book-test", data)

    # Le fichier doit être importable et avoir les bonnes valeurs
    result = read_config("book-test")
    assert result["title"] == "New Title"
    assert result["author"] == "Marco Belghiti"
    assert result["characters"][0]["id"] == "hero"
    assert result["page_sequence"][0]["file"] == "book-test_hero.png"


def test_write_config_preserves_non_editable_sections(fake_book, monkeypatch):
    """Les sections TITLE_PAGE_LINES etc. doivent être préservées."""
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", fake_book)

    data = {
        "title": "Changed Title",
        "subtitle": "Sub",
        "author": "Marco Belghiti",
        "testpen": "tp.png",
        "images_folder": "book-test",
        "characters": [],
        "page_sequence": [],
    }
    write_config("book-test", data)
    result = read_config("book-test")
    # TITLE_PAGE_LINES doit être identique à ce qui était dans FAKE_CONFIG
    # Note: après round-trip JSON, les tuples deviennent des listes
    assert result["title_page_lines"] == [["Test Book", 120, True, [0, 0, 0]]]


def test_write_config_images_dir_uses_relative_path(fake_book, monkeypatch):
    """IMAGES_DIR doit utiliser pathlib.Path(__file__).parent... (jamais hardcodé)."""
    import pipeline.config_io as cio
    monkeypatch.setattr(cio, "ROOT", fake_book)

    data = {
        "title": "T", "subtitle": "S", "author": "A",
        "testpen": "tp.png", "images_folder": "book-test",
        "characters": [], "page_sequence": [],
    }
    write_config("book-test", data)

    content = (fake_book / "books" / "book-test" / "config.py").read_text()
    assert 'pathlib.Path(__file__).parent.parent.parent' in content
    assert '"book-test"' in content
    # Jamais de chemin absolu hardcodé
    assert '/Users/' not in content
