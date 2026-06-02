# StoreFront: custom photo upload + orders store + admin auth

Date: 2026-06-02
Status: approved

## Goal

Make the customer storefront capture a real order (child name + photo), persist it,
and price it, while adding email-allowlist authentication for the admin surface so the
app can be hosted on a VPS with multiple collaborators. Keep the flow linear, simple to
operate, and easy to evolve toward Stripe.

## Non-goals (this iteration)

- No real payment charge. Payment stays a stub; orders move pending -> paid via the stub.
- No book generation triggered on payment (later turn).
- No Stripe code yet, but the schema is Stripe-ready (order has reference/amount/currency/status).

## Architecture

### Storage: `storefront/db.py` (stdlib sqlite3)

Single file `.storefront/storefront.db` (gitignored). A `Database` wrapper opens one
connection (`check_same_thread=False`) guarded by a `threading.Lock`, and runs idempotent
`CREATE TABLE IF NOT EXISTS` migrations on construction.

Tables:

- `orders(reference PK, slug, email, child_name, photo_path, page_count,
  amount_cents, currency, status, created_at, updated_at)`
  status in (pending, paid, failed).
- `auth_codes(email PK, code_hash, salt, expires_at, attempts)` — SQLite-backed
  replacement for the JSON AuthStore.
- `admins(email PK, created_at)` — allowlist, seeded from settings on startup.

Helper functions (pure where possible, db-bound where needed):
`create_order(db, ...) -> reference`, `get_order(db, reference)`,
`set_order_status(db, reference, status)`, `list_orders(db, limit)`.

### Auth store migration

`storefront/auth.py` keeps `request_code`/`verify_code`/`generate_code`/`_hash`
unchanged in signature, but gains a `SqliteAuthStore(db)` implementing the same
`put/get/delete` interface as the old `AuthStore`. The JSON `AuthStore` stays for
backward-compatible tests but the app wires `SqliteAuthStore`.

### Admin auth: `storefront/admin.py`

- `seed_admins(db, emails)` upserts the allowlist.
- `is_admin(db, email) -> bool`.
- Reuses the existing one-time-code machinery (request/verify) but gated so only
  allowlisted emails can request a code.
- Separate signed cookie `sf_admin` (distinct from customer `sf_session`).

### Routes (dashboard/app.py)

Customer:
- `POST /store/{slug}/order` (multipart child_name + photo) -> creates pending order,
  saves photo to `.storefront/orders/{reference}/photo.png`, returns
  `{reference, amount, currency}`.
- `POST /store/{slug}/checkout` now requires an existing `reference` (from the order),
  creates the stub checkout, and marks the order `paid` (stub success is immediate).

Admin:
- `GET /admin/login` (email form).
- `POST /admin/auth/request` (403 if email not allowlisted), `POST /admin/auth/verify`
  (sets `sf_admin` cookie).
- `GET /admin/orders` + `GET /admin/orders/{reference}/photo` (admin-gated).
- `_require_admin(request)` gate applied to admin pages/mutations when
  `storefront.admin.enabled` is true. Default disabled (local dev unchanged).

### Settings (settings.example.json)

```jsonc
"storefront": {
  "session_secret": "CHANGE_ME",
  "admin": { "enabled": false, "emails": ["you@example.com"] },
  "https": false,
  "payment_provider": "stub",
  "smtp": { "host": "", "port": 587, "username": "", "password": "",
            "from_addr": "no-reply@example.com", "use_tls": true }
}
```

When `https` is true, auth cookies are set with `secure=true`.

## Data flow

```
Customer /store/{slug}
  -> enter child name + photo -> POST /store/{slug}/order
       -> validate published, re-encode PNG, save photo, compute_price, INSERT pending
       -> {reference, amount, currency}
  -> email code auth (existing) -> sf_session
  -> POST /store/{slug}/checkout {reference}
       -> stub provider create_checkout -> set_order_status(paid) -> redirect mock url

Admin (VPS, admin.enabled=true)
  -> GET /admin/login -> code -> sf_admin cookie
  -> _require_admin gates /, /book, /settings, /storybook, /stream, /api mutations
  -> GET /admin/orders -> list + photo thumbnails
```

## Testing

- `tests/test_storefront_db.py`: migrations idempotent, order CRUD, status update,
  sqlite auth roundtrip + rate limit.
- `tests/test_storefront_admin.py`: allowlist gate (non-admin 403), admin cookie verify.
- extend `tests/test_storefront_api.py`: order creation returns pending + amount,
  checkout marks paid, admin gate (401/redirect when enabled), admin orders page lists.

## Your-side actions (VPS) — delivered as explicit, ready-to-run steps at the end.

## Stripe readiness

Order carries reference/amount_cents/currency/status. A future `StripePaymentProvider`
+ `POST /store/webhook/stripe` looks up the order by reference and flips status. No
schema migration needed.
