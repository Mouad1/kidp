from storyforge.types import Variable, PageBeat, Template, CharacterSheet, PageSpec


def test_template_holds_pages_and_variables():
    tpl = Template(
        name="Demo",
        mode="color",
        language_default="fr",
        art_style="watercolor",
        variables=[Variable(key="HERO_NAME", label="Name", type="text", options=[])],
        pages=[PageBeat(beat="intro", text="{HERO_NAME} smiles", image_prompt="{HERO} smiling")],
    )
    assert tpl.mode == "color"
    assert tpl.variables[0].key == "HERO_NAME"
    assert tpl.pages[0].beat == "intro"


def test_pagespec_defaults_reference_required_true():
    spec = PageSpec(page_number=1, text="hi", image_prompt="hero", mode="color")
    assert spec.reference_required is True


def test_character_sheet_fields():
    sheet = CharacterSheet(
        descriptor="boy, 7, curly hair",
        canonical_portrait_png=b"\x89PNG",
        art_style="watercolor",
        source_photos=[b"\x89PNG"],
    )
    assert sheet.descriptor.startswith("boy")
    assert sheet.canonical_portrait_png == b"\x89PNG"
