# StoryForge — Storefront, Multilingual, Page Count, Cover & Pricing

**Date:** 2026-06-01
**Status:** Approved (design), pending spec review
**Author:** pairing session

## Summary

Evolve StoryForge from an admin-only generation flow into a two-sided product:

- **Admin** keeps the existing `/storybook` + `/book/<slug>` flow to build catalog
  stories (eventually "in conversation with an agent").
- **Customers** get a separate, linear storefront: browse pre-built stories,
  personalize with their child's name + photo, preview the output and cover,
  see the price, then validate and proceed to Stripe payment.

The work is split into three workstreams, built in this order:

- **A — Admin generation flow**: fix multilingual output (bug), add page-count
  option, add cover generation/preview.
- **B — Pricing module** (shared): admin-configurable cost model + live price.
- **C — Customer storefront**: catalog → personalize → preview → price → payment.

A and B are specified in detail here. C is sketched here and will get its own
detailed spec + plan before implementation.

## Decisions (locked)

| Topic | Decision |
|---|---|
| Sequencing | A first, then C; B is a shared module |
| Languages | Customer/admin selects target languages; auto-translate each page |
| Page count | Customer-selectable: **8 / 12 / 16 / 24**; **dynamic expansion** of a base narrative |
| Price model | `price = printing_cost × markup_multiplier` |
| Pricing inputs | **Admin-configurable settings**: B&W per-page, color per-page, paper-quality, cover cost, markup, currency. Start with placeholder values. |
| Storefront end state | Preview personalized output → validate → **Stripe** payment (Stripe designed/stubbed in C) |
| Storefront location | Same dashboard app, separate customer route |
| Authentication | **Email + confirmation code** (free via SMTP). SMS/phone deferred: no free provider, revisit only if one is found. |

---

## Workstream A — Admin generation flow

### A1 · Multilingual fix (bug)

**Problem.** `build_book` writes every page as
`{"fr": spec.text, "ar": "", "en": spec.text, "es": ""}` with `languages: ["fr"]`.
The English template text lands in both the French and English slots; Arabic and
Spanish stay empty; the config claims "French only." The rendered book and the
"Informations du Livre" checkboxes disagree.

**Design.**

1. Templates declare a `source_language` (default = existing `language_default`).
2. A translation step produces per-page text for every selected target language.
   - Reuse `dashboard/translate.py: translate_text(text, target_langs) -> dict`.
   - Wrap it behind an injectable `translate_fn` so tests use a fake (no network),
     consistent with the existing `ImageGenerator` / `_analyze_provider` DI seams.
   - New helper `storyforge/i18n.py: translate_pages(specs, source_language,
     target_languages, translate_fn) -> list[dict[str, str]]`. Returns one
     `{lang: text}` dict per page. The source language keeps the original text;
     other selected languages are filled by `translate_fn`.
3. `build_book` gains parameters `languages: list[str]` and
   `page_texts: list[dict[str, str]] | None`.
   - When `page_texts` is provided, each page's `text` dict is built from it and
     `languages` is written verbatim.
   - When `None` (back-compat), behaves as a single-language book in
     `source_language`.
4. The wizard (`storybook.html`) gains language checkboxes (fr, en, es, ar). The
   `/stream/storyforge/{name}/generate` endpoint reads the selected languages,
   runs `translate_pages`, and passes results to `build_book`.

**Result.** `languages` always equals the selected set; only selected slots are
populated; checkboxes and rendered pages match.

### A2 · Page count (dynamic expansion)

**Goal.** Customer picks 8 / 12 / 16 / 24 pages; the engine renders the chosen
story at that length.

**Design.**

- A template holds a **base narrative** (its existing `pages` beats).
- New `storyforge/expand.py: expand_narrative(template, variables, hero,
  page_count, text_fn) -> list[PageSpec]`:
  - Uses a text model to expand/condense the base beats into exactly
    `page_count` page specs, preserving the story arc and all `{HERO}` /
    `{HERO_NAME}` / variable tokens.
  - `text_fn` is injected (fake in tests). Output is validated: exactly
    `page_count` specs, every reserved/declared token still resolvable.
- `resolve(...)` stays the pure path for the no-expansion case. When a
  `page_count` is requested that differs from the template length,
  `expand_narrative` runs first, then the normal resolution/substitution applies.
- Wizard adds a page-count `<select>` (8/12/16/24). Default = template length.

**Risk.** Dynamic expansion quality varies. Mitigation: validation pass +
admin preview before publishing to the catalog. Flagged for plan-level attention.

### A3 · Cover generation & preview

**Design.**

- Reuse `pipeline/cover.py`'s prompt builder, but pass the child's
  `canonical_portrait.png` as a reference image so the cover hero matches the
  interior pages. Title is added programmatically (never embedded in the image).
- New `storyforge/cover.py: generate_cover(title, hero, image_gen) -> bytes`,
  using the injected `ImageGenerator` (fake in tests).
- Saved to `output/<book_name>_COVER.png`. Served via a no-cache endpoint
  `GET /api/storyforge/{name}/cover` (mirrors the existing portrait endpoint).
- Generated as the final step of `/stream/storyforge/{name}/generate`; the wizard
  shows an inline cover preview when done.

---

## Workstream B — Pricing module (shared)

**Design.**

- New `pipeline/pricing.py` (pure, no I/O):
  `compute_price(page_count, color, paper_quality, has_cover, settings) -> dict`
  returning `{currency, printing_cost, price}` where
  `printing_cost = cover_cost + page_count × per_page(color, paper_quality)` and
  `price = round(printing_cost × markup_multiplier, 2)`.
- **Admin-configurable settings** (in `settings.json`, editable on the settings
  page) under a `pricing` block:
  - `currency` (e.g. "USD")
  - `bw_per_page`, `color_per_page`
  - `paper_quality`: named tiers → per-page multiplier (e.g. `standard: 1.0`,
    `premium: 1.3`)
  - `cover_cost`
  - `markup_multiplier`
  - All seeded with **placeholder** values, clearly editable in the admin UI.
- `GET /api/pricing?page_count=&color=&paper_quality=&has_cover=` returns the
  computed price. Admin flow and storefront both call it live (no page reload).

---

## Workstream C — Customer storefront (sketch)

Detailed in a follow-up spec. High-level shape:

- **Catalog.** Books the admin marks as published become catalog entries.
  Customer route `GET /store` lists them (title, cover thumbnail, base price).
- **Personalize.** `GET /store/{slug}` is a linear wizard reusing StoryForge
  pieces: child name + photo → build hero → pick language(s) + page count →
  live price.
- **Preview.** Personalized page previews + cover, with the child's name and
  likeness.
- **Checkout.** "Validate & pay" → **Stripe** (provider chosen; integration and
  the exact preview/watermark policy designed in the C spec). Stubbed endpoint
  acceptable for the first iteration.
- The admin `/book/<slug>` page stays admin-only; customers never see it.

### Authentication (customer)

Detailed in the workstream C spec; decisions locked here:

- **Method.** Email + one-time confirmation code (6 digits, short TTL). Free to
  run over SMTP; no third-party billing.
- **Why not SMS.** Every reliable SMS gateway (Twilio, Vonage, etc.) charges per
  message; there is no production-grade free SMS API. Phone/SMS auth is deferred
  and revisited only if a genuinely free, reliable provider is found. The auth
  module is designed with a pluggable `code_sender` interface so an SMS sender can
  be added later without reworking the flow.
- **Flow.** Enter email → receive code → enter code → session established. Required
  before checkout/payment; browsing the catalog stays public.
- **Storage.** Minimal: email, verified-at, and a hashed/expiring code record.
  No passwords. Session via signed cookie.
- **DI.** `code_sender` (email/SMS) and the clock are injectable so tests never
  send real email and can assert code generation/expiry deterministically.

---

## Testing

All network behind injection; no test hits an API.

- `i18n.translate_pages`: fake `translate_fn`; asserts source kept, targets filled,
  only selected languages present.
- `build_book`: with `page_texts` + `languages`, asserts config `languages` and
  per-page `text` slots match exactly; back-compat path still works.
- `expand_narrative`: fake `text_fn`; asserts exact page count and token integrity.
- `cover.generate_cover`: fake `ImageGenerator`; asserts PNG bytes + portrait used
  as reference.
- `pricing.compute_price`: pure unit tests across B&W/color, paper tiers, cover
  on/off, markup; rounding.
- Dashboard API: language selection end-to-end, page-count selection, cover
  endpoint, `/api/pricing`.
- Non-regression: existing fixed-length, single-language generation still works
  when no page count / single language is selected.

## Out of scope (this spec)

- Full Stripe integration and order persistence (workstream C spec).
- Customer authentication implementation (workstream C spec; decisions locked above).
- Agent-conversation authoring of catalog stories (future).
- Print/fulfillment.
