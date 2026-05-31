import pytest
from storyforge.identity import build_hero, save_sheet, load_sheet, validate_photos
from storyforge.imagegen import FakeImageGenerator, PNG_MAGIC

PNG = PNG_MAGIC + b"rest-of-bytes"


def test_validate_photos_rejects_empty():
    with pytest.raises(ValueError, match="at least one"):
        validate_photos([])


def test_validate_photos_rejects_too_many():
    with pytest.raises(ValueError, match="most 3"):
        validate_photos([PNG, PNG, PNG, PNG])


def test_build_hero_uses_photos_as_reference_and_returns_sheet():
    gen = FakeImageGenerator()
    sheet = build_hero(
        photos=[PNG],
        art_style="watercolor",
        gen=gen,
        analyze=lambda photos: "boy, 7, curly hair",
    )
    assert sheet.descriptor == "boy, 7, curly hair"
    assert sheet.art_style == "watercolor"
    assert sheet.canonical_portrait_png.startswith(PNG_MAGIC)
    assert gen.calls[0]["reference_images"] == [PNG]
    assert "watercolor" in gen.calls[0]["prompt"]


def test_save_and_load_sheet_round_trip(tmp_path):
    gen = FakeImageGenerator()
    sheet = build_hero([PNG], "watercolor", gen, lambda p: "desc")
    save_sheet(tmp_path, sheet)
    loaded = load_sheet(tmp_path)
    assert loaded.descriptor == "desc"
    assert loaded.canonical_portrait_png == sheet.canonical_portrait_png
    assert loaded.art_style == "watercolor"
