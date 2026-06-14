import pytest
from fastapi.testclient import TestClient
from storyforge.types import Template, PageBeat, Variable
from storyforge.errors import TemplateError


FAKE_TEMPLATE = Template(
    name="My Story",
    mode="color",
    language_default="fr",
    art_style="painterly",
    variables=[Variable(key="HERO_NAME", label="Child's name", type="text", default="Zoe")],
    pages=[
        PageBeat(beat="opening", text="Il était une fois {HERO_NAME}...", image_prompt="a forest"),
        PageBeat(beat="middle", text="Et puis {HERO_NAME} marcha.", image_prompt="a river"),
    ],
    slug="my-book",
)


FAKE_CONFIG = {
    "title": "My Story",
    "published": True,
    "pages": [
        {"text": {"fr": "Il était une fois Zoe...", "en": "Once upon a time Zoe..."}},
        {"text": {"fr": "Et puis Zoe marcha.", "en": "And then Zoe walked."}},
    ],
    "languages": ["fr", "en"],
}


@pytest.fixture()
def preview_client(tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "ROOT", tmp_path)
    monkeypatch.setattr(app_module, "_store_read_config", lambda name: FAKE_CONFIG)
    monkeypatch.setattr(app_module, "_sf_load_template", lambda slug: FAKE_TEMPLATE)
    img_dir = tmp_path / "images" / "my-book"
    img_dir.mkdir(parents=True)
    (img_dir / "my-book_page_1.png").write_bytes(b"PNG")
    return TestClient(app_module.app)


def test_preview_returns_200_with_page_text(preview_client):
    r = preview_client.get("/store/my-book/story-preview")
    assert r.status_code == 200
    assert "Il était une fois Zoe" in r.text
    assert "Et puis Zoe marcha" in r.text


def test_preview_uses_default_hero_name_when_config_missing_translation(preview_client, monkeypatch):
    import dashboard.app as app_module
    # Config has no English text for page 1, so it should fall back to template text
    # with the default hero name substituted.
    cfg_no_en = {
        "title": "My Story",
        "published": True,
        "pages": [
            {"text": {"fr": "Bonjour {HERO_NAME}"}},
            {"text": {"fr": "Salut {HERO_NAME}"}},
        ],
        "languages": ["fr", "en"],
    }
    monkeypatch.setattr(app_module, "_store_read_config", lambda name: cfg_no_en)
    r = preview_client.get("/store/my-book/story-preview?lang=en")
    assert r.status_code == 200
    assert "Bonjour Zoe" in r.text


def test_preview_shows_image_url_for_existing_page(preview_client):
    r = preview_client.get("/store/my-book/story-preview")
    assert "/images/my-book/my-book_page_1.png" in r.text


def test_preview_language_switch_uses_config_translation(preview_client):
    r = preview_client.get("/store/my-book/story-preview?lang=en")
    assert r.status_code == 200
    assert "Once upon a time Zoe" in r.text


def test_preview_404_unpublished(tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "_store_read_config",
                        lambda name: {"title": "X", "published": False, "pages": []})
    r = TestClient(app_module.app).get("/store/my-book/story-preview")
    assert r.status_code == 404


def test_preview_404_book_not_found(tmp_path, monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "_store_read_config",
                        lambda name: (_ for _ in ()).throw(FileNotFoundError()))
    r = TestClient(app_module.app).get("/store/my-book/story-preview")
    assert r.status_code == 404


def test_preview_404_missing_template(monkeypatch):
    import dashboard.app as app_module
    monkeypatch.setattr(app_module, "_store_read_config",
                        lambda name: {"title": "X", "published": True, "pages": [1]})
    def raise_err(slug):
        raise TemplateError("not found")
    monkeypatch.setattr(app_module, "_sf_load_template", raise_err)
    r = TestClient(app_module.app).get("/store/my-book/story-preview")
    assert r.status_code == 404
