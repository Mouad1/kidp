from storyforge.templates import load_template


def test_example_template_loads_and_validates():
    tpl = load_template("brave-little-explorer")
    assert tpl.name
    assert tpl.mode in ("color", "lineart")
    assert len(tpl.pages) >= 3
    keys = {v.key for v in tpl.variables}
    assert "HERO_NAME" in keys
