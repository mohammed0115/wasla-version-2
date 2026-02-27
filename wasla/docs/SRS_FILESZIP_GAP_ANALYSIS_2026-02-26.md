# SRS Gap Analysis (from `/home/mohamed/Desktop/files.zip`)

Date: 2026-02-26

## Source SRS inputs reviewed
- `/home/mohamed/Desktop/_srs_input/files/01_dashboard.txt`
- `/home/mohamed/Desktop/_srs_input/files/02_products.txt`
- `/home/mohamed/Desktop/_srs_input/files/03_orders.txt`
- `/home/mohamed/Desktop/_srs_input/files/04_shipping.txt`
- `/home/mohamed/Desktop/_srs_input/files/05_wallet.txt`
- `/home/mohamed/Desktop/_srs_input/files/06_reviews.txt`
- `/home/mohamed/Desktop/_srs_input/files/07_app_store.txt`
- `/home/mohamed/Desktop/_srs_input/files/08_settings.txt`
- Extracted SRS PDFs (via `pdftotext`) in `/home/mohamed/Desktop/_srs_input/files/_text/`

## High-confidence gaps

### 1) Dashboard KPI mismatch (Wallet Balance + Active Shipments missing)
**SRS asks:** Dashboard must show Revenue, Orders Today, Wallet Balance, Active Shipments.

**Current state:** dashboard overview shows sales/orders/revenue/visitors/conversion, but not wallet balance or active shipments.
- Evidence: `templates/dashboard/pages/overview.html`
- Evidence: `apps/tenants/application/dto/merchant_dashboard_metrics.py`

**Gap:** Partial implementation of dashboard scenario.

---

### 2) Product auto-status based on stock not implemented
**SRS asks:** Auto status based on stock.

**Current state:** product creation writes `is_active` from input; inventory `in_stock` is tracked, but no automatic sync rule to disable/hide product when stock reaches zero.
- Evidence: `apps/catalog/services/product_service.py`
- Evidence: `apps/catalog/models.py` (`Inventory` with `in_stock` but no product-status rule)

**Gap:** Auto-status behavior missing.

---

### 3) Order lifecycle graph is incomplete vs SRS chain
**SRS asks:** `Created → Paid → Processing → Shipped → Delivered → Completed` and reject invalid transitions.

**Current state:** transitions validation exists, but:
- there is no `created` status (uses `pending`),
- `processing -> shipped` is not allowed in transition map (`processing: []`).
- Evidence: `apps/orders/models.py`
- Evidence: `apps/orders/services/order_lifecycle_service.py`

**Gap:** Lifecycle sequence is not fully represented.

---

### 4) Shipping lifecycle visibility/update endpoints are incomplete
**SRS asks:** assign carrier, track shipment status, view tracking numbers.

**Current state:** only shipment creation endpoint is exposed (`POST /orders/{id}/ship/`). No dedicated API for listing shipments, fetching tracking timeline, or status updates.
- Evidence: `apps/shipping/urls.py`
- Evidence: `apps/shipping/views/api.py`

**Gap:** Tracking/status management is only partially exposed.

---

### 5) Reviews moderation workflow not exposed to owner/manager operations
**SRS asks:** review pending then approve/reject by owner/manager.

**Current state:** create + list-approved APIs exist; approve/reject service methods exist but are not exposed via moderation API/UI with role checks.
- Evidence: `apps/reviews/urls.py`
- Evidence: `apps/reviews/views/api.py`
- Evidence: `apps/reviews/services/review_service.py`

**Gap:** moderation workflow is backend-only, not operationally usable.

---

### 6) Settings module incomplete vs SRS scope
**SRS asks:** store profile, users & roles, subscription & billing (owner-only).

**Current state:** tenant web routes cover store info and setup payment/shipping, but no merchant-facing users/roles management routes in tenant URLs.
- Evidence: `apps/tenants/urls.py`

**Gap:** users/roles management (merchant-facing) is missing from settings flow.

## Medium-confidence gaps (from broader SRS PDFs)

### 7) Product category requirement not enforced
**SRS asks:** Product must belong to at least one category.

**Current state:** `create_product(..., categories=None)` allows creating products without categories.
- Evidence: `apps/catalog/services/product_service.py`

---

### 8) Product visibility states richer than boolean
**SRS asks:** enabled / disabled / hidden.

**Current state:** product uses `is_active` boolean (2-state), no explicit `hidden` state.
- Evidence: `apps/catalog/models.py`

## Covered (not a gap)
- Wallet pending vs available balance is implemented and tested.
  - Evidence: `apps/wallet/models.py`, `apps/wallet/tests.py`
- Plugin feature/plan gating is implemented.
  - Evidence: `apps/plugins/services/lifecycle_service.py`
- Invalid order transitions are validated.
  - Evidence: `apps/orders/services/order_lifecycle_service.py`, `apps/orders/tests.py`

## Recommended implementation order
1. Dashboard wallet + active shipments KPI.
2. Order state machine fix (`processing -> shipped`, explicit `created` alias/mapping decision).
3. Shipping tracking/status APIs + merchant UI listing.
4. Reviews moderation API/UI with owner/manager RBAC.
5. Product auto-status-on-stock + category-required validation.
6. Tenant settings users/roles management screens and APIs.
