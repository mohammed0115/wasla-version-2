# Wasla v0.1 — Gap List (Checklist)

> Use this list to verify completeness against the prototype + AI requirements.

## P0 — Must work end-to-end (Demo/Release blocker)
- [ ] Registration scenario (Screens 1→13) completes without errors
  - [ ] User created, Profile created
  - [ ] Persona fields saved (country/legal/existing/channel/category)
  - [ ] Plan selection creates Tenant + Membership(owner) + Subscription
- [ ] Store Setup Wizard Step 1→4 works and persists:
  - [ ] tenant.setup_step advances correctly
  - [ ] tenant.setup_completed set to True at activation
- [ ] Storefront basic pages load (home/product/detail/cart/checkout)
- [ ] Admin QA Dashboard loads and actions work:
  - [ ] Seed demo products
  - [ ] Build/Update Index
  - [ ] Run Visual Search KPI
- [ ] Visual Search UI:
  - [ ] Upload image -> results shown
  - [ ] Filters apply correctly (price/color/brightness/white_background)
  - [ ] Load more works (12 → 24)

## P1 — Language & UX
- [ ] i18n complete coverage:
  - [ ] Arabic and English supported across all user-facing templates
  - [ ] No mixed-language pages when switching language
  - [ ] RTL/LTR layout switches correctly
- [ ] Marketing/landing pages are persuasive for merchants
- [ ] Copywriting and CTA consistency

## P2 — AI quality & performance
- [ ] CLIP enabled environment works (optional) with acceptable latency
- [ ] Embedding + search latency < 3s on typical catalog sizes
- [ ] Attribute extraction correctness (color, brightness, white background)
- [ ] Re-indexing incremental (fingerprint) works

## P3 — Multi-tenancy & security
- [ ] Store scoping everywhere (tenant isolation)
- [ ] Domain mapping flows (custom domain + SSL) implemented/verified
- [ ] Permissions for merchant dashboards (owner vs staff)

## P4 — Payments & settlements
- [ ] Payment integrations are correctly stubbed or implemented
- [ ] Settlement reports accuracy + fee calculation

## P5 — Quality and maintainability
- [ ] Codebase follows SOLID/DRY: duplicated code removed
- [ ] Facade/services used where external providers exist
- [ ] Tests cover the main flows and run in CI
