from storyforge.types import PageSpec, Template, PageBeat, Variable
from storyforge.i18n import translate_pages, backfill_missing_translations


def _spec(n, text):
    return PageSpec(page_number=n, text=text, image_prompt="x", mode="color")


def fake_translate(text, target_langs):
    return {lang: f"{lang}:{text}" for lang in target_langs}


def test_source_language_keeps_original_and_targets_filled():
    specs = [_spec(1, "Hello"), _spec(2, "World")]
    out = translate_pages(specs, "en", ["en", "fr", "ar"], fake_translate)

    assert out[0]["en"] == "Hello"
    assert out[0]["fr"] == "fr:Hello"
    assert out[0]["ar"] == "ar:Hello"
    assert set(out[0].keys()) == {"en", "fr", "ar"}
    assert out[1]["en"] == "World"
    assert out[1]["fr"] == "fr:World"


def test_single_language_skips_translate_fn():
    called = []

    def spy(text, langs):
        called.append((text, langs))
        return {}

    specs = [_spec(1, "Solo")]
    out = translate_pages(specs, "en", ["en"], spy)

    assert out == [{"en": "Solo"}]
    assert called == []


def fake_template(language_default="fr"):
    return Template(
        name="T",
        mode="color",
        language_default=language_default,
        art_style="paint",
        variables=[Variable(key="HERO_NAME", label="Name", type="text", default="Zoe")],
        pages=[PageBeat(beat="b", text="Bonjour {HERO_NAME}", image_prompt="x")],
    )


def test_backfill_adds_missing_translations():
    cfg = {
        "title": "T",
        "published": True,
        "languages": ["fr"],
        "pages": [{"page_number": 1, "text": {"fr": "Bonjour Zoe"}, "image_prompt": "x"}],
    }
    written = []

    def read_fn(name):
        return cfg

    def write_fn(name, data):
        written.append(data)

    def load_tpl(name):
        return fake_template("fr")

    added = backfill_missing_translations(
        "my-book", read_fn, write_fn, load_tpl, fake_translate, ["fr", "en", "es"]
    )

    assert set(added) == {"en", "es"}
    assert written
    updated = written[-1]
    assert updated["languages"] == ["en", "es", "fr"]
    assert updated["pages"][0]["text"]["en"] == "en:Bonjour Zoe"
    assert updated["pages"][0]["text"]["es"] == "es:Bonjour Zoe"


def test_backfill_returns_empty_when_all_languages_present():
    cfg = {
        "title": "T",
        "published": True,
        "languages": ["fr", "en"],
        "pages": [{"page_number": 1, "text": {"fr": "Bonjour", "en": "Hello"}, "image_prompt": "x"}],
    }

    def read_fn(name):
        return cfg

    def write_fn(name, data):
        raise AssertionError("should not write")

    added = backfill_missing_translations(
        "my-book", read_fn, write_fn, lambda n: fake_template("fr"), fake_translate, ["fr", "en"]
    )

    assert added == []
