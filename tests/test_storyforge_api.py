import io
import pathlib
import shutil
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import dashboard.app as appmod
from storyforge.imagegen import FakeImageGenerator

ROOT = pathlib.Path(__file__).parent.parent
client = TestClient(appmod.app)


def _image_bytes(fmt: str = "PNG") -> bytes:
    im = Image.new("RGB", (8, 8), color=(255, 255, 255))
    buf = io.BytesIO()
    im.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def fake_backend(monkeypatch):
    fake = FakeImageGenerator()
    monkeypatch.setattr(appmod, "_backend_provider", lambda: fake)
    monkeypatch.setattr(appmod, "_analyze_provider", lambda photos: "boy, 7, curly hair")
    yield fake


@pytest.fixture
def cleanup():
    name = "test-storyforge-api"
    yield name
    shutil.rmtree(ROOT / "books" / name, ignore_errors=True)
    shutil.rmtree(ROOT / "images" / name, ignore_errors=True)


def test_list_templates_includes_example():
    r = client.get("/api/storyforge/templates")
    assert r.status_code == 200
    slugs = [t["slug"] for t in r.json()]
    assert "brave-little-explorer" in slugs


def test_upload_photos_then_build_hero(cleanup):
    name = cleanup
    png = _image_bytes("PNG")
    r = client.post(
        f"/api/storyforge/{name}/photos",
        files=[("photos", ("a.png", io.BytesIO(png), "image/png"))],
    )
    assert r.status_code == 200
    assert (ROOT / "books" / name / "hero" / "source_0.png").exists()

    r = client.get(f"/stream/storyforge/{name}/hero?slug=brave-little-explorer")
    assert r.status_code == 200
    assert (ROOT / "books" / name / "hero" / "canonical_portrait.png").exists()


def test_generate_book_creates_config(cleanup, fake_backend):
    name = cleanup
    png = _image_bytes("PNG")
    client.post(f"/api/storyforge/{name}/photos",
                files=[("photos", ("a.png", io.BytesIO(png), "image/png"))])
    client.get(f"/stream/storyforge/{name}/hero?slug=brave-little-explorer")

    r = client.get(
        f"/stream/storyforge/{name}/generate",
        params={
            "slug": "brave-little-explorer",
            "title": "Sami's Adventure",
            "author": "Tester",
            "HERO_NAME": "Sami",
            "SETTING": "enchanted forest",
            "VALUE": "courage",
            "SIDEKICK": "fox",
        },
    )
    assert r.status_code == 200
    assert (ROOT / "books" / name / "config.py").exists()
    from pipeline.config_io import read_config
    cfg = read_config(name)
    assert cfg["title"] == "Sami's Adventure"
    assert len(cfg["pages"]) == 4


def test_upload_jpeg_is_normalized_to_png(cleanup):
    name = cleanup
    jpeg = _image_bytes("JPEG")

    r = client.post(
        f"/api/storyforge/{name}/photos",
        files=[("photos", ("a.jpg", io.BytesIO(jpeg), "image/jpeg"))],
    )

    assert r.status_code == 200
    stored = (ROOT / "books" / name / "hero" / "source_0.png").read_bytes()
    assert stored.startswith(b"\x89PNG\r\n\x1a\n")


def test_pricing_endpoint_returns_price():
    r = client.get("/api/pricing", params={
        "page_count": 16, "color": True, "paper_quality": "standard", "has_cover": True,
    })
    assert r.status_code == 200
    body = r.json()
    assert "price" in body
    assert "currency" in body
    assert body["price"] > 0


def test_pricing_endpoint_rejects_unknown_paper():
    r = client.get("/api/pricing", params={"page_count": 8, "paper_quality": "ultra"})
    assert r.status_code == 400


def test_generate_with_languages_and_cover(cleanup, fake_backend, monkeypatch):
    name = cleanup
    monkeypatch.setattr(
        appmod, "_translate_provider",
        lambda text, langs: {lang: f"{lang}:{text}" for lang in langs},
    )
    png = _image_bytes("PNG")
    client.post(f"/api/storyforge/{name}/photos",
                files=[("photos", ("a.png", io.BytesIO(png), "image/png"))])
    client.get(f"/stream/storyforge/{name}/hero?slug=brave-little-explorer")

    r = client.get(
        f"/stream/storyforge/{name}/generate",
        params={
            "slug": "brave-little-explorer",
            "title": "Sami's Adventure",
            "author": "Tester",
            "languages": "en,fr",
            "HERO_NAME": "Sami",
            "SETTING": "enchanted forest",
            "VALUE": "courage",
            "SIDEKICK": "fox",
        },
    )
    assert r.status_code == 200
    assert "ERROR" not in r.text

    from pipeline.config_io import read_config
    cfg = read_config(name)
    assert cfg["languages"] == ["en", "fr"]
    assert cfg["pages"][0]["text"]["fr"]  # source language keeps original
    assert not cfg["pages"][0]["text"]["fr"].startswith("en:")
    assert cfg["pages"][0]["text"]["en"].startswith("en:")
    assert cfg["pages"][0]["text"]["es"] == ""

    cover = client.get(f"/api/storyforge/{name}/cover")
    assert cover.status_code == 200
    assert cover.content.startswith(b"\x89PNG\r\n\x1a\n")

