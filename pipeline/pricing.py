"""Admin-configurable pricing. Pure functions; values come from settings.json."""


def default_pricing_settings() -> dict:
    """Placeholder values. Admins edit these on the settings page."""
    return {
        "currency": "USD",
        "bw_per_page": 0.012,
        "color_per_page": 0.07,
        "paper_quality": {"standard": 1.0, "premium": 1.5},
        "cover_cost": 1.00,
        "markup_multiplier": 2.5,
    }


def compute_price(
    page_count: int,
    color: bool,
    paper_quality: str,
    has_cover: bool,
    settings: dict,
) -> dict:
    quality = settings.get("paper_quality", {})
    if paper_quality not in quality:
        raise ValueError(f"Unknown paper quality: {paper_quality!r}")
    multiplier = quality[paper_quality]
    per_page = settings["color_per_page"] if color else settings["bw_per_page"]
    cover = settings["cover_cost"] if has_cover else 0.0

    printing_cost = round(cover + page_count * per_page * multiplier, 2)
    price = round(printing_cost * settings["markup_multiplier"], 2)
    return {
        "currency": settings.get("currency", "USD"),
        "printing_cost": printing_cost,
        "price": price,
    }
