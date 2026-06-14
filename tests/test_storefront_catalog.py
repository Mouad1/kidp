from storefront.catalog import list_catalog, CatalogEntry


def fake_reader(name):
    data = {
        "alpha": {"title": "Alpha", "published": True, "pages": [1, 2, 3, 4],
                  "category": "story"},
        "beta": {"title": "Beta", "published": False, "pages": [1, 2],
                 "category": "story"},
    }
    return data[name]


def test_only_published_books_listed():
    entries = list_catalog(["alpha", "beta"], read_fn=fake_reader)
    assert [e.slug for e in entries] == ["alpha"]
    assert isinstance(entries[0], CatalogEntry)
    assert entries[0].title == "Alpha"
    assert entries[0].page_count == 4
