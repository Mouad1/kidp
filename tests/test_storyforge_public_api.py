import storyforge


def test_public_api_surface():
    for name in [
        "build_hero", "save_sheet", "load_sheet",
        "load_template", "list_templates", "validate_template",
        "resolve", "generate_page", "build_book",
        "FakeImageGenerator",
    ]:
        assert hasattr(storyforge, name), f"missing public export: {name}"


def test_public_api_exports_new_helpers():
    for name in ("translate_pages", "expand_narrative", "generate_cover"):
        assert hasattr(storyforge, name)
        assert name in storyforge.__all__


def test_settings_json_has_pricing_block():
    import json, pathlib
    root = pathlib.Path(__file__).parent.parent
    data = json.loads((root / "settings.json").read_text())
    assert "pricing" in data
    p = data["pricing"]
    for key in ("currency", "bw_per_page", "color_per_page",
                "paper_quality", "cover_cost", "markup_multiplier"):
        assert key in p
