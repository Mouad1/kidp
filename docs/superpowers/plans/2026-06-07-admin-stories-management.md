# Admin Stories Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `/admin/stories` page where the admin can see all story templates and toggle published/unpublished status inline without page reload.

**Architecture:** New `GET /admin/stories` route in `dashboard/app.py` builds an entries list from `_list_books()` + `_book_status()` + order counts grouped from `_sf_list_orders()`. New `admin_stories.html` template renders cards with inline JS toggle calling the existing `POST /api/storyforge/{name}/publish` endpoint. Cross-link added to `admin_orders.html` header.

**Tech Stack:** FastAPI, Jinja2, Tailwind CSS (CDN), plain `fetch()` JS — no new dependencies.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `tests/test_admin_stories.py` | Route tests (redirect, content, auth bypass) |
| Modify | `dashboard/app.py` (append before `if __name__`) | New `GET /admin/stories` route |
| Create | `dashboard/templates/admin_stories.html` | Cards grid + inline toggle JS |
| Modify | `dashboard/templates/admin_orders.html` | Add "📖 Stories" nav link in header |

---

## Task 1: Tests (TDD red phase)

**Files:**
- Create: `tests/test_admin_stories.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_admin_stories.py
import pathlib
import pytest
from fastapi.testclient import TestClient

import dashboard.app as appmod

ROOT = pathlib.Path(__file__).parent.parent
client = TestClient(appmod.app)

SECRET = "test-secret"

BOOKS = {
    "lolo-hero":    {"title": "Lolo Hero",     "category": "story",    "in_sequence": 22, "published": True},
    "joudia-world": {"title": "Joudia's World", "category": "storyforge","in_sequence": 18, "published": False},
}


@pytest.fixture
def stories_env(tmp_path, monkeypatch):
    from storefront.db import Database
    db = Database(tmp_path / "storefront.db")
    monkeypatch.setattr(appmod, "_store_db", lambda: db)
    monkeypatch.setattr(appmod, "_store_session_secret", lambda: SECRET)
    monkeypatch.setattr(appmod, "_load_storefront_settings", lambda: {})
    monkeypatch.setattr(appmod, "_list_books", lambda: list(BOOKS))
    monkeypatch.setattr(appmod, "_book_status", lambda name: {"name": name, **BOOKS[name]})
    client.cookies.clear()
    return db


def _admin_cookie():
    from storefront.session import sign
    import datetime as dt
    return sign({"email": "admin@test.com", "admin": True}, SECRET, now=dt.datetime.utcnow())


def _login_admin():
    client.cookies.set("sf_admin", _admin_cookie())


def test_admin_stories_redirects_without_session(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_admin_enabled", lambda: True)
    r = client.get("/admin/stories", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


def test_admin_stories_returns_200_with_valid_session(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    r = client.get("/admin/stories")
    assert r.status_code == 200


def test_admin_stories_lists_all_book_slugs(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    r = client.get("/admin/stories")
    assert "lolo-hero" in r.text
    assert "joudia-world" in r.text


def test_admin_stories_published_shows_depublier(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    r = client.get("/admin/stories")
    assert "Dépublier" in r.text


def test_admin_stories_unpublished_shows_publier(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    r = client.get("/admin/stories")
    assert "Publier" in r.text


def test_admin_stories_shows_order_counts(stories_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin",
                        lambda request: {"email": "admin@test.com", "admin": True})
    # Insert one order for lolo-hero
    from storefront.db import create_order
    import datetime as dt
    create_order(stories_env, reference="lolo-hero-abc123", slug="lolo-hero",
                 email="a@b.com", child_name="Lina", photo_path="/tmp/p.png",
                 page_count=22, amount_cents=1200, currency="USD",
                 now=dt.datetime.utcnow())
    r = client.get("/admin/stories")
    assert "1" in r.text  # 1 commande for lolo-hero
```

- [ ] **Step 2: Run tests to confirm they all fail**

```bash
python3 -m pytest tests/test_admin_stories.py -v 2>&1 | tail -20
```

Expected: all 6 tests FAIL with `404` or `AttributeError` (route doesn't exist yet).

---

## Task 2: Route in `dashboard/app.py`

**Files:**
- Modify: `dashboard/app.py` — insert before the `if __name__ == "__main__":` block at the end

- [ ] **Step 3: Add the `/admin/stories` route**

Find the line `if __name__ == "__main__":` (last ~10 lines of file) and insert before it:

```python
@app.get("/admin/stories", response_class=HTMLResponse)
def admin_stories(request: Request):
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)
    all_orders = _sf_list_orders(_store_db(), limit=10000)
    order_counts: dict[str, int] = {}
    for o in all_orders:
        order_counts[o["slug"]] = order_counts.get(o["slug"], 0) + 1
    entries = []
    for name in _list_books():
        status = _book_status(name)
        entries.append({
            "slug":        name,
            "title":       status.get("title", name),
            "category":    status.get("category", ""),
            "page_count":  status.get("in_sequence", 0),
            "order_count": order_counts.get(name, 0),
            "published":   status.get("published", False),
        })
    return templates.TemplateResponse(
        request=request, name="admin_stories.html", context={"entries": entries},
    )
```

- [ ] **Step 4: Run tests — redirect + 200 tests should now pass**

```bash
python3 -m pytest tests/test_admin_stories.py::test_admin_stories_redirects_without_session tests/test_admin_stories.py::test_admin_stories_returns_200_with_valid_session -v
```

Expected: both PASS. The content tests still fail (template missing).

---

## Task 3: Template `admin_stories.html`

**Files:**
- Create: `dashboard/templates/admin_stories.html`

- [ ] **Step 5: Create the template**

```html
<!DOCTYPE html>
<html lang="en">

<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Stories · Admin</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>

<body class="bg-gray-50 text-gray-900 min-h-screen">
  <header class="bg-white border-b border-gray-200 px-6 py-4">
    <div class="max-w-5xl mx-auto flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="text-2xl">📖</span>
        <h1 class="text-lg font-bold">Stories</h1>
      </div>
      <div class="flex items-center gap-4 text-sm">
        <a href="/admin/orders" class="text-indigo-600 hover:text-indigo-800">← Orders</a>
        <a href="/" class="text-indigo-600 hover:text-indigo-800">← Dashboard</a>
      </div>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-6 py-8">
    {% if not entries %}
    <div class="bg-white border border-dashed border-gray-300 rounded-xl p-12 text-center text-gray-500">
      Aucune story trouvée.
    </div>
    {% else %}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {% for e in entries %}
      <div
        class="bg-white rounded-xl border-2 p-5 flex flex-col gap-3 {% if e.published %}border-emerald-300{% else %}border-gray-200{% endif %}"
        data-slug="{{ e.slug }}"
        data-published="{{ 'true' if e.published else 'false' }}"
      >
        <div class="flex items-start justify-between gap-2">
          <h2 class="font-bold text-base leading-tight">{{ e.title }}</h2>
          <span class="shrink-0 px-2 py-0.5 rounded-full text-xs font-semibold
            {% if e.published %}bg-emerald-100 text-emerald-700{% else %}bg-gray-100 text-gray-500{% endif %}">
            {% if e.published %}Publié{% else %}Masqué{% endif %}
          </span>
        </div>

        <div class="flex flex-wrap gap-1.5 text-xs">
          <span class="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{{ e.category }}</span>
          <span class="bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{{ e.page_count }} pages</span>
        </div>

        <div class="text-xs text-gray-500">
          📦 <strong>{{ e.order_count }}</strong> commande{{ 's' if e.order_count != 1 else '' }}
        </div>

        <div class="text-xs text-gray-400 font-mono">{{ e.slug }}</div>

        <div class="mt-auto pt-2">
          <button
            onclick="togglePublish(this)"
            class="w-full py-1.5 rounded-lg text-sm font-medium transition-colors
              {% if e.published %}bg-red-50 text-red-700 hover:bg-red-100{% else %}bg-emerald-600 text-white hover:bg-emerald-700{% endif %}"
          >
            {% if e.published %}Dépublier{% else %}Publier{% endif %}
          </button>
          <p class="text-red-600 text-xs mt-1 hidden" data-error></p>
        </div>
      </div>
      {% endfor %}
    </div>
    {% endif %}
  </main>

  <script>
    async function togglePublish(btn) {
      const card = btn.closest("[data-slug]");
      const slug = card.dataset.slug;
      const currently = card.dataset.published === "true";
      const next = !currently;
      const errEl = card.querySelector("[data-error]");

      btn.disabled = true;
      const origText = btn.textContent.trim();
      btn.textContent = "...";
      errEl.classList.add("hidden");

      try {
        const r = await fetch(`/api/storyforge/${slug}/publish?published=${next}`, { method: "POST" });
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Erreur serveur");

        // Update card state inline
        card.dataset.published = String(next);
        const badge = card.querySelector("span[class*='rounded-full']");

        if (next) {
          card.classList.replace("border-gray-200", "border-emerald-300");
          badge.className = badge.className.replace("bg-gray-100 text-gray-500", "bg-emerald-100 text-emerald-700");
          badge.textContent = "Publié";
          btn.className = btn.className.replace("bg-emerald-600 text-white hover:bg-emerald-700", "bg-red-50 text-red-700 hover:bg-red-100");
          btn.textContent = "Dépublier";
        } else {
          card.classList.replace("border-emerald-300", "border-gray-200");
          badge.className = badge.className.replace("bg-emerald-100 text-emerald-700", "bg-gray-100 text-gray-500");
          badge.textContent = "Masqué";
          btn.className = btn.className.replace("bg-red-50 text-red-700 hover:bg-red-100", "bg-emerald-600 text-white hover:bg-emerald-700");
          btn.textContent = "Publier";
        }
      } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.remove("hidden");
        btn.textContent = origText;
      } finally {
        btn.disabled = false;
      }
    }
  </script>
</body>
</html>
```

- [ ] **Step 6: Run all admin stories tests**

```bash
python3 -m pytest tests/test_admin_stories.py -v 2>&1 | tail -15
```

Expected: all 6 PASS.

---

## Task 4: Cross-link in `admin_orders.html`

**Files:**
- Modify: `dashboard/templates/admin_orders.html`

- [ ] **Step 7: Add "📖 Stories" nav link in orders header**

Current header in `admin_orders.html` (line ~16–20):
```html
      <a href="/" class="text-sm text-indigo-600 hover:text-indigo-800">← Dashboard</a>
```

Replace with:
```html
      <div class="flex items-center gap-4 text-sm">
        <a href="/admin/stories" class="text-indigo-600 hover:text-indigo-800">📖 Stories</a>
        <a href="/" class="text-indigo-600 hover:text-indigo-800">← Dashboard</a>
      </div>
```

- [ ] **Step 8: Run full test suite**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -10
```

Expected: all tests pass, 0 failures.

---

## Task 5: Manual smoke test

- [ ] **Step 9: Start server and verify**

```bash
make storefront
```

1. Open `http://localhost:8000/admin/orders` → header should show "📖 Stories" link
2. Click "📖 Stories" → lands on `/admin/stories`
3. All books listed with title, category, page count, order count, slug
4. Click "Publier" on an unpublished book → button changes to "Dépublier", border turns green, no reload
5. Open `http://localhost:8000/store` → book now appears in catalog
6. Click "Dépublier" → book disappears from catalog on next `/store` load

- [ ] **Step 10: Commit**

```bash
git add dashboard/app.py dashboard/templates/admin_stories.html dashboard/templates/admin_orders.html tests/test_admin_stories.py
git commit -m "feat(admin): add /admin/stories page with inline publish toggle"
```
