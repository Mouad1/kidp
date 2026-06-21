# Store Summary + Admin Emails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display per-story `intro_text` on catalog cards, and add an admin UI at `/admin/settings` to list/add/remove admin emails.

**Architecture:** Task 1 resolves `intro_text` by language in the `store_catalog` Python route and surfaces it in the card template. Task 2 adds two DB helpers (`list_admins`, `remove_admin`) to `storefront/admin.py`, three API endpoints in `dashboard/app.py`, and a new `admin_settings.html` template.

**Tech Stack:** FastAPI, Jinja2, SQLite (via `storefront.db.Database`), Tailwind CSS (CDN)

## Global Constraints

- No new dependencies — stdlib + existing packages only
- `intro_text` in config can be `dict` (e.g. `{"fr": "...", "en": "..."}`) or plain `str` — must handle both
- All admin routes must call `_require_admin(request)` and redirect to `/admin/login` on None
- Admin email operations affect SQLite `admins` table only — do NOT write to `settings.json`
- Template style: match existing admin templates (Tailwind CDN, `bg-gray-100`, same card style as `admin_orders.html`)

---

## Task 1: Per-story intro_text on catalog cards

**Files:**
- Modify: `dashboard/app.py` — `store_catalog` route (~line 1482), add `intro_text_display` per entry
- Modify: `dashboard/templates/store_catalog.html:86` — replace `{{ i18n.catalog_subtitle }}` with `{{ e.intro_text_display }}`
- Test: `tests/test_storefront_api.py` — add `test_catalog_shows_intro_text`

**Interfaces:**
- Consumes: `cfg.get("intro_text", "")` — already in `e.intro_text` in view loop
- Produces: `e.intro_text_display: str` — resolved string passed to template, falls back to `i18n.catalog_subtitle` if empty

- [ ] **Step 1: Write the failing test**

Add to `tests/test_storefront_api.py` (in the `store_env` fixture block, after `test_catalog_lists_only_published`):

```python
def test_catalog_shows_intro_text(store_env, monkeypatch):
    catalog = store_env["catalog"]
    catalog["alpha"]["intro_text"] = {"fr": "Une histoire magique.", "en": "A magical story."}
    r = client.get("/store", headers={"Accept-Language": "fr"})
    assert r.status_code == 200
    assert "Une histoire magique." in r.text
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_storefront_api.py::test_catalog_shows_intro_text -v
```

Expected: FAIL — `"Une histoire magique."` not in response (template shows `i18n.catalog_subtitle` instead).

- [ ] **Step 3: Add `_resolve_intro_text` helper and update `store_catalog` route**

In `dashboard/app.py`, add this helper just before the `store_catalog` route (~line 1474):

```python
def _resolve_intro_text(intro_text, lang: str, fallback: str) -> str:
    """Resolve intro_text (dict or str) to a display string for the given language."""
    if isinstance(intro_text, dict):
        return (intro_text.get(lang)
                or intro_text.get("fr")
                or next(iter(intro_text.values()), "")
                or fallback)
    if isinstance(intro_text, str) and intro_text.strip():
        return intro_text.strip()
    return fallback
```

In `store_catalog`, replace the `view.append(...)` block to add `intro_text_display`:

```python
    for e in entries:
        cfg = _store_read_config(e.slug)
        book_languages = cfg.get("languages") or ["fr"]
        quote = _store_price_quote(e.page_count)
        cover_url = f"/images/{e.slug}/{e.slug}_page_1.png"
        fallback = _sf_i18n.get_strings(lang).get("catalog_subtitle", "")
        view.append({
            "slug": e.slug,
            "title": e.title,
            "page_count": e.page_count,
            "category": e.category,
            "price_display": quote["display"],
            "languages": book_languages,
            "all_languages": supported,
            "intro_text": cfg.get("intro_text", ""),
            "intro_text_display": _resolve_intro_text(
                cfg.get("intro_text", ""), lang, fallback
            ),
            "cover_url": cover_url,
        })
```

- [ ] **Step 4: Update template**

In `dashboard/templates/store_catalog.html`, replace line 86:

```html
<!-- before -->
<p class="text-sm text-stone-500 mb-4 line-clamp-3 flex-1">
  {{ i18n.catalog_subtitle }}
</p>

<!-- after -->
<p class="text-sm text-stone-500 mb-4 line-clamp-3 flex-1">
  {{ e.intro_text_display }}
</p>
```

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest tests/test_storefront_api.py -v
```

Expected: all pass including `test_catalog_shows_intro_text`.

- [ ] **Step 6: Commit**

```bash
git add dashboard/app.py dashboard/templates/store_catalog.html tests/test_storefront_api.py
git commit -m "feat(store): show per-story intro_text on catalog cards"
```

---

## Task 2: Admin email management UI

**Files:**
- Modify: `storefront/admin.py` — add `list_admins(db)` and `remove_admin(db, email)`
- Modify: `storefront/__init__.py` — export `list_admins`, `remove_admin`
- Modify: `dashboard/app.py` — add `GET /admin/settings`, `GET /api/admin/emails`, `POST /api/admin/emails`, `DELETE /api/admin/emails/{email}`
- Create: `dashboard/templates/admin_settings.html`
- Test: `tests/test_storefront_api.py` — add 4 tests for the API endpoints

**Interfaces:**
- Consumes: `_store_db()`, `_require_admin(request)`, `_sf_is_admin` — all already in `dashboard/app.py`
- Produces:
  - `list_admins(db: Database) -> list[dict]` — returns `[{"email": str, "created_at": str}, ...]`
  - `remove_admin(db: Database, email: str) -> None`
  - `GET /api/admin/emails` → `{"emails": [{"email": str, "created_at": str}]}`
  - `POST /api/admin/emails` body `{"email": str}` → `{"added": True, "email": str}`
  - `DELETE /api/admin/emails/{email}` → `{"removed": True, "email": str}`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_storefront_api.py`:

```python
def test_admin_list_emails_returns_list(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: {"email": "admin", "admin": True})
    from storefront.admin import seed_admins
    import datetime as dt
    seed_admins(store_env["db"], ["test@example.com"], now=dt.datetime.utcnow())
    r = client.get("/api/admin/emails")
    assert r.status_code == 200
    emails = [e["email"] for e in r.json()["emails"]]
    assert "test@example.com" in emails


def test_admin_add_email(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: {"email": "admin", "admin": True})
    r = client.post("/api/admin/emails", json={"email": "new@example.com"})
    assert r.status_code == 200
    assert r.json()["added"] is True
    assert appmod._sf_is_admin(store_env["db"], "new@example.com")


def test_admin_remove_email(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: {"email": "admin", "admin": True})
    from storefront.admin import seed_admins
    import datetime as dt
    seed_admins(store_env["db"], ["todelete@example.com"], now=dt.datetime.utcnow())
    r = client.delete("/api/admin/emails/todelete@example.com")
    assert r.status_code == 200
    assert not appmod._sf_is_admin(store_env["db"], "todelete@example.com")


def test_admin_email_endpoints_require_auth(store_env, monkeypatch):
    monkeypatch.setattr(appmod, "_require_admin", lambda request: None)
    assert client.get("/api/admin/emails").status_code == 401
    assert client.post("/api/admin/emails", json={"email": "x@y.com"}).status_code == 401
    assert client.delete("/api/admin/emails/x@y.com").status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_storefront_api.py::test_admin_list_emails_returns_list tests/test_storefront_api.py::test_admin_add_email tests/test_storefront_api.py::test_admin_remove_email tests/test_storefront_api.py::test_admin_email_endpoints_require_auth -v
```

Expected: 4 FAIL — routes do not exist yet.

- [ ] **Step 3: Add `list_admins` and `remove_admin` to `storefront/admin.py`**

```python
def list_admins(db: Database) -> list[dict]:
    rows = db.query_all("SELECT email, created_at FROM admins ORDER BY created_at ASC")
    return [{"email": row["email"], "created_at": row["created_at"]} for row in rows]


def remove_admin(db: Database, email: str) -> None:
    normalized = (email or "").strip().lower()
    if normalized:
        db.execute("DELETE FROM admins WHERE email = ?", (normalized,))
```

- [ ] **Step 4: Note on `Database.query_all`**

`Database.query_all` already exists in `storefront/db.py` — no change needed. The `list_admins` implementation in Step 3 uses `query_all` (confirmed).

- [ ] **Step 5: Export from `storefront/__init__.py`**

In `storefront/__init__.py`, add `list_admins` and `remove_admin` to imports and `__all__`:

```python
from storefront.admin import seed_admins, is_admin, list_admins, remove_admin

__all__ = [
    # ... existing ...
    "seed_admins", "is_admin", "list_admins", "remove_admin",
]
```

- [ ] **Step 6: Add API endpoints to `dashboard/app.py`**

Import `list_admins` and `remove_admin` at the top of `dashboard/app.py` alongside existing `storefront.admin` imports:

```python
from storefront.admin import seed_admins as _sf_seed_admins, is_admin as _sf_is_admin, \
    list_admins as _sf_list_admins, remove_admin as _sf_remove_admin
```

Add three endpoints after the existing `admin_stats` route (~line 2064):

```python
@app.get("/api/admin/emails")
def admin_list_emails(request: Request):
    if _require_admin(request) is None:
        raise HTTPException(status_code=401, detail="Admin sign in required.")
    rows = _sf_list_admins(_store_db())
    return {"emails": rows}


class AdminEmailModel(BaseModel):
    email: str


@app.post("/api/admin/emails")
def admin_add_email(request: Request, data: AdminEmailModel):
    if _require_admin(request) is None:
        raise HTTPException(status_code=401, detail="Admin sign in required.")
    normalized = (data.email or "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
        raise HTTPException(status_code=400, detail="Invalid email address.")
    _sf_seed_admins(_store_db(), [normalized], now=_dt.datetime.utcnow())
    return {"added": True, "email": normalized}


@app.delete("/api/admin/emails/{email}")
def admin_remove_email(email: str, request: Request):
    if _require_admin(request) is None:
        raise HTTPException(status_code=401, detail="Admin sign in required.")
    normalized = (email or "").strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Invalid email.")
    _sf_remove_admin(_store_db(), normalized)
    return {"removed": True, "email": normalized}


@app.get("/admin/settings", response_class=HTMLResponse)
def admin_settings_page(request: Request):
    if _require_admin(request) is None:
        return RedirectResponse(url="/admin/login", status_code=303)
    emails = _sf_list_admins(_store_db())
    return templates.TemplateResponse(
        request=request, name="admin_settings.html",
        context={"emails": emails},
    )
```

- [ ] **Step 7: Create `dashboard/templates/admin_settings.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Admin Settings</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 text-gray-900 min-h-screen">
  <div class="max-w-2xl mx-auto px-6 py-10">

    <div class="mb-6">
      <a href="/admin" class="text-indigo-600 hover:text-indigo-800 text-sm">← Dashboard</a>
    </div>

    <h1 class="text-2xl font-bold mb-8">Settings</h1>

    <!-- Admin Emails -->
    <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h2 class="text-lg font-semibold mb-1">Admin Emails</h2>
      <p class="text-sm text-gray-500 mb-5">
        These emails can sign in to the admin dashboard via one-time code.
        Removing an email revokes access immediately.
      </p>

      <ul id="email-list" class="divide-y divide-gray-100 mb-6">
        {% for row in emails %}
        <li class="flex items-center justify-between py-3" id="row-{{ loop.index }}">
          <span class="text-sm font-medium text-gray-800">{{ row.email }}</span>
          <button onclick="removeEmail('{{ row.email }}')"
                  class="text-xs text-red-500 hover:text-red-700 font-medium px-3 py-1 rounded-lg hover:bg-red-50 transition">
            Remove
          </button>
        </li>
        {% else %}
        <li class="py-3 text-sm text-gray-400" id="empty-state">No admin emails configured.</li>
        {% endfor %}
      </ul>

      <div class="flex gap-3">
        <input id="new-email" type="email" placeholder="new@example.com"
               class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500" />
        <button onclick="addEmail()"
                class="bg-gray-900 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-gray-700 transition">
          Add
        </button>
      </div>
      <p id="msg" class="text-sm text-red-600 mt-3 hidden"></p>
    </div>

  </div>

  <script>
    function showMsg(text, ok = false) {
      const el = document.getElementById("msg");
      el.textContent = text;
      el.className = `text-sm mt-3 ${ok ? "text-green-600" : "text-red-600"}`;
      el.classList.remove("hidden");
      setTimeout(() => el.classList.add("hidden"), 3000);
    }

    async function addEmail() {
      const input = document.getElementById("new-email");
      const email = input.value.trim();
      if (!email) return;
      const r = await fetch("/api/admin/emails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        showMsg(d.detail || "Failed to add email.");
        return;
      }
      input.value = "";
      const list = document.getElementById("email-list");
      const empty = document.getElementById("empty-state");
      if (empty) empty.remove();
      const li = document.createElement("li");
      li.className = "flex items-center justify-between py-3";
      li.innerHTML = `
        <span class="text-sm font-medium text-gray-800">${email}</span>
        <button onclick="removeEmail('${email}')"
                class="text-xs text-red-500 hover:text-red-700 font-medium px-3 py-1 rounded-lg hover:bg-red-50 transition">
          Remove
        </button>`;
      list.appendChild(li);
      showMsg("Email added.", true);
    }

    async function removeEmail(email) {
      if (!confirm(`Remove ${email}?`)) return;
      const r = await fetch(`/api/admin/emails/${encodeURIComponent(email)}`, { method: "DELETE" });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        showMsg(d.detail || "Failed to remove email.");
        return;
      }
      document.querySelectorAll("#email-list li").forEach(li => {
        if (li.querySelector("span")?.textContent.trim() === email) li.remove();
      });
      showMsg("Email removed.", true);
    }
  </script>
</body>
</html>
```

- [ ] **Step 8: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: all pass including the 4 new admin email tests.

- [ ] **Step 9: Commit**

```bash
git add storefront/admin.py storefront/__init__.py storefront/db.py \
        dashboard/app.py dashboard/templates/admin_settings.html \
        tests/test_storefront_api.py
git commit -m "feat(admin): add email management UI at /admin/settings"
```
