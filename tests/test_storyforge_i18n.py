from storyforge.types import PageSpec
from storyforge.i18n import translate_pages


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
