import pathlib
import pytest

from storyforge.builder import build_book
from storyforge.types import PageSpec, CharacterSheet
from pipeline.config_io import read_config

ROOT = pathlib.Path(__file__).parent.parent


@pytest.fixture
def cleanup_book():
    name = "test-storyforge-tmp"
    yield name
    import shutil
    shutil.rmtree(ROOT / "books" / name, ignore_errors=True)
    shutil.rmtree(ROOT / "images" / name, ignore_errors=True)


def test_build_book_writes_config_and_images(cleanup_book):
    name = cleanup_book
    hero = CharacterSheet(descriptor="boy", canonical_portrait_png=b"\x89PNG", art_style="watercolor")
    specs = [
        PageSpec(page_number=1, text="Sami begins", image_prompt="boy starts", mode="color"),
        PageSpec(page_number=2, text="Sami learns", image_prompt="boy learns", mode="color"),
    ]
    page_pngs = [b"\x89PNG-1", b"\x89PNG-2"]

    build_book(
        book_name=name,
        title="Sami's Adventure",
        author="Test Author",
        mode="color",
        specs=specs,
        page_pngs=page_pngs,
        hero=hero,
    )

    assert (ROOT / "images" / name / f"{name}_page_1.png").read_bytes() == b"\x89PNG-1"
    assert (ROOT / "images" / name / f"{name}_page_2.png").read_bytes() == b"\x89PNG-2"

    cfg = read_config(name)
    assert cfg["title"] == "Sami's Adventure"
    assert cfg["author"] == "Test Author"
    assert cfg["category"] == "story"
    assert len(cfg["pages"]) == 2


def test_build_book_writes_selected_languages_and_page_texts(cleanup_book):
    name = cleanup_book
    hero = CharacterSheet(descriptor="boy", canonical_portrait_png=b"\x89PNG", art_style="watercolor")
    specs = [
        PageSpec(page_number=1, text="Sami begins", image_prompt="boy starts", mode="color"),
        PageSpec(page_number=2, text="Sami learns", image_prompt="boy learns", mode="color"),
    ]
    page_texts = [
        {"en": "Sami begins", "fr": "Sami commence"},
        {"en": "Sami learns", "fr": "Sami apprend"},
    ]
    build_book(
        book_name=name, title="T", author="A", mode="color",
        specs=specs, page_pngs=[b"\x89PNG-1", b"\x89PNG-2"], hero=hero,
        languages=["en", "fr"], page_texts=page_texts,
    )
    cfg = read_config(name)
    assert cfg["languages"] == ["en", "fr"]
    assert cfg["pages"][0]["text"]["en"] == "Sami begins"
    assert cfg["pages"][0]["text"]["fr"] == "Sami commence"
    assert cfg["pages"][0]["text"]["es"] == ""
    assert cfg["pages"][0]["text"]["ar"] == ""
    assert cfg["pages"][1]["text"]["fr"] == "Sami apprend"


def test_build_book_lineart_uses_coloring_category(cleanup_book):
    name = cleanup_book
    hero = CharacterSheet(descriptor="boy", canonical_portrait_png=b"\x89PNG", art_style="watercolor")
    specs = [PageSpec(page_number=1, text="hi", image_prompt="boy", mode="lineart")]
    build_book(name, "T", "A", "lineart", specs, [b"\x89PNG-1"], hero)
    cfg = read_config(name)
    assert cfg["category"] == "coloring"
