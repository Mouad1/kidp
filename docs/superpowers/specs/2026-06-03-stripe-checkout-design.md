# Stripe Checkout Integration — Design Spec

Date: 2026-06-03
Branch: feat/storyforge-storefront-auth-payment

## Goal

Replace `StubPaymentProvider` with a real Stripe Checkout (hosted) integration.
Stub remains available for local dev without Stripe keys.

## Payment Flow

```
POST /store/{slug}/checkout
  → get_payment_provider(settings) → StripePaymentProvider
  → stripe.checkout.Session.create(client_reference_id=reference, ...)
  → returns CheckoutSession(status="pending", url="https://checkout.stripe.com/...")
  → route returns {status:"pending", url:...} — does NOT mark paid

User pays on Stripe-hosted page →
  → Stripe POST /store/webhook/stripe
  → verify Stripe-Signature (skip if STRIPE_WEBHOOK_SECRET unset — dev mode)
  → event type == "checkout.session.completed"
  → client_reference_id → set_order_status(reference, "paid")
```

Stub flow unchanged: `create_checkout()` returns `status="paid"`, route marks paid immediately.

## Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `STRIPE_SECRET_KEY` | Yes (stripe mode) | `sk_test_…` for test, `sk_live_…` for prod |
| `STRIPE_WEBHOOK_SECRET` | No | `whsec_…` — if absent, signature check skipped (dev only) |

Keys never in `settings.json`. Always in `.env.local` (git-ignored).

## Files Changed

### `storefront/payment.py`

- Update `PaymentProvider` Protocol: `create_checkout` gains `success_url: str = ""` and `cancel_url: str = ""`
- `StubPaymentProvider`: ignores new params, returns `status="pending"` url=`/store/checkout/mock/{reference}` — **no behavior change**
- Add `StripePaymentProvider`:
  - Constructor: `__init__(self, secret_key: str)`
  - `create_checkout()`: calls `stripe.checkout.Session.create()` with `client_reference_id=reference`, `line_items` built from `amount`/`currency`, returns `CheckoutSession(status="pending", url=session.url)`
- Update `get_payment_provider(settings)`: if `payment_provider == "stripe"`, read `STRIPE_SECRET_KEY` from env, raise `RuntimeError` if missing, return `StripePaymentProvider(secret_key)`

### `dashboard/app.py`

**Route `POST /store/{slug}/checkout`** — two changes:
1. Pass `success_url` and `cancel_url` to `create_checkout()`, constructed from `request.base_url`
2. Replace unconditional `set_order_status("paid")` with conditional: only mark paid if `checkout.status == "paid"` (stub path). Stripe path returns `"pending"` — webhook marks paid.

**New route `POST /store/webhook/stripe`**:
- Read raw body + `Stripe-Signature` header
- If `STRIPE_WEBHOOK_SECRET` set: verify with `stripe.Webhook.construct_event()`, raise 400 on failure
- If not set: parse JSON directly (dev mode, log warning once)
- On `checkout.session.completed`: get `client_reference_id`, call `set_order_status(reference, "paid")`
- Always return `{"received": True}` with 200

### `settings.example.json`

Document `"payment_provider": "stripe"` as valid option alongside `"stub"`.

### `tests/test_stripe_payment.py` (new)

- `test_stripe_provider_calls_stripe_api`: mock `stripe.checkout.Session.create`, assert correct params
- `test_stripe_provider_returns_pending`: assert returned `CheckoutSession.status == "pending"`
- `test_webhook_marks_order_paid`: POST fake `checkout.session.completed` event, assert order status = `"paid"`
- `test_webhook_rejects_bad_signature`: POST with wrong signature when secret set, assert 400
- `test_webhook_skips_signature_check_in_dev`: POST without secret configured, assert 200

## Dependencies

- `stripe` Python SDK — add to `requirements.txt` or install directly

## No DB Migration

`client_reference_id` in Stripe Session maps to our `reference`. No new columns needed.

## Backward Compatibility

- Existing tests use `"payment_provider": "stub"` monkeypatch — unaffected
- `StubPaymentProvider` behavior unchanged
- Webhook route is additive — no breaking changes
