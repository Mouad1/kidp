from dataclasses import dataclass
from typing import Callable


@dataclass
class CatalogEntry:
    slug: str
    title: str
    page_count: int
    category: str


def list_catalog(book_names: list[str], read_fn: Callable[[str], dict]) -> list[CatalogEntry]:
    out: list[CatalogEntry] = []
    for name in book_names:
        cfg = read_fn(name)
        if not cfg.get("published"):
            continue
        out.append(CatalogEntry(
            slug=name,
            title=cfg.get("title", name),
            page_count=len(cfg.get("pages", [])),
            category=cfg.get("category", "story"),
        ))
    return out
