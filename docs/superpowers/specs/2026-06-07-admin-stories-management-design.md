# Admin Stories Management — Design Spec

**Date:** 2026-06-07
**Branch:** feat/storyforge-storefront-auth-payment
**Status:** Approved

## Summary

Add `/admin/stories` page allowing the admin to see all story templates and toggle their
published/unpublished status. Published stories appear in the public `/store` catalog;
unpublished ones are hidden.

## Context

- `/store` catalog filters on `published=True` via `storefront/catalog.py:list_catalog()`
- `POST /api/storyforge/{name}/publish?published=true/false` already exists and works
- Admin UI pattern established by `admin_orders.html` (Tailwind, plain HTML + fetch)
- Auth guard `_require_admin(request)` already in place

## Approach

Standalone page `/admin/stories` — new route + new template. Follows the exact pattern
of `/admin/orders`. No shared nav partial (YAGNI — only 2 admin pages).

## Route

```
GET /admin/stories
```

- Requires admin session via `_require_admin(request)` → redirect `/admin/login` if absent
- Loads all books via `_list_books()` + `_book_status()` (title, category, page count, slug, published)
- Counts orders per book slug from `_sf_list_orders()` (group by slug in Python)
- Renders `admin_stories.html` with `entries` list

Each entry passed to template:
```python
{
  "slug": str,       # book name / URL slug
  "title": str,
  "category": str,
  "page_count": int, # len(page_sequence)
  "order_count": int,
  "published": bool,
}
```

## Template — `admin_stories.html`

**Header:** same structure as `admin_orders.html`
- Title: `📖 Stories`
- Nav links: `← Orders` → `/admin/orders` and `← Dashboard` → `/`

**Grid layout:** `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4`

**Each card:**
- Published: green border (`border-emerald-300`), green badge "Publié"
- Unpublished: gray border, gray badge "Masqué"
- Content: title (bold), category + page count badges, order count line, slug in monospace
- Action button:
  - If published → "Dépublier" (red-soft: `bg-red-50 text-red-700 hover:bg-red-100`)
  - If unpublished → "Publier" (green: `bg-emerald-600 text-white hover:bg-emerald-700`)

**Empty state:** "Aucune story trouvée." centered dashed box (same pattern as orders).

## Toggle Behavior (inline JS, no page reload)

On button click:
1. Disable button, set text to "..."
2. `fetch('POST /api/storyforge/{slug}/publish?published={!current}', { method: 'POST' })`
3. On success:
   - Swap button label + color classes
   - Swap card border + badge
   - Update `data-published` attribute on card
4. On error:
   - Re-enable button, restore original label
   - Show inline error text below button: `text-red-600 text-xs`

## Cross-links

- `admin_orders.html` header gets a new link: `📖 Stories` → `/admin/stories`

## Tests

- `test_admin_stories.py` (new file):
  - `GET /admin/stories` without session → 303 redirect to `/admin/login`
  - `GET /admin/stories` with valid admin session → 200, all book slugs in HTML
  - Published book → "Dépublier" button in HTML
  - Unpublished book → "Publier" button in HTML
  - Existing `test_storefront_api.py` covers the publish API endpoint

## Out of Scope

- Reordering stories in the catalog
- Per-story analytics / revenue
- Cover image preview on card (no images stored in accessible path)
- Shared admin nav partial (defer until 3+ admin pages)
