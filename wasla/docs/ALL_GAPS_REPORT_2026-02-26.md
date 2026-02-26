# All Gaps Report

Date: 2026-02-26
Branch: optimizatio

## Scope
This report consolidates gap findings from the SRS files analysis and shows current status after the latest implementation rounds.

## Source Reports
- SRS gap baseline: [docs/SRS_FILESZIP_GAP_ANALYSIS_2026-02-26.md](docs/SRS_FILESZIP_GAP_ANALYSIS_2026-02-26.md)
- Architecture gap baseline: [docs/ARCH_GAP_ANALYSIS.md](docs/ARCH_GAP_ANALYSIS.md)

## SRS Gap Matrix (Complete List)

### Closed

1) Dashboard KPI mismatch (Wallet Balance + Active Shipments)
- Status: Closed
- Implemented in:
  - apps/tenants/application/dto/merchant_dashboard_metrics.py
  - apps/tenants/application/use_cases/get_merchant_dashboard_metrics.py
  - apps/tenants/infrastructure/repositories/django_wallet_repository.py
  - apps/tenants/infrastructure/repositories/django_shipment_repository.py
  - templates/dashboard/pages/overview.html

2) Product auto-status based on stock
- Status: Closed
- Implemented in:
  - apps/catalog/models.py (Inventory save syncs Product.is_active)
  - apps/catalog/services/product_service.py
  - apps/catalog/services/variant_service.py
  - apps/catalog/tests/test_inventory_auto_status.py

3) Order lifecycle incomplete vs SRS chain
- Status: Closed (for pending/paid/processing/shipped/delivered/completed flow)
- Implemented in:
  - apps/orders/services/order_lifecycle_service.py
  - apps/orders/tests.py
- Note: System still uses pending instead of created as stored status.

4) Shipping lifecycle visibility/update endpoints incomplete
- Status: Closed
- Implemented in:
  - apps/shipping/views/api.py
  - apps/shipping/urls.py
  - config/urls.py
  - apps/shipping/tests.py

5) Reviews moderation workflow exposed to owner/manager operations
- Status: Closed
- Implemented in:
  - apps/reviews/views/api.py
  - apps/reviews/serializers.py
  - apps/reviews/urls.py
  - apps/reviews/tests.py
  - apps/tenants/management/commands/seed_permissions.py
  - config/urls.py

### Open

6) Settings module users & roles management (merchant-facing)
- Status: Open
- Missing:
  - Merchant-facing routes/UI/actions for users and roles management in settings flow.

7) Product category requirement enforcement
- Status: Open
- Missing:
  - Hard validation that product must belong to at least one category.

8) Product visibility states richer than boolean (enabled/disabled/hidden)
- Status: Open
- Missing:
  - 3-state visibility model and migration from boolean active flag.

## Counts
- Total SRS gaps tracked: 8
- Closed: 5
- Open: 3

## Priority to Complete Remaining Gaps
1. Settings users/roles merchant management
2. Category-required validation for product creation/update
3. Product visibility state model expansion

## Change Evidence (Recent Commits)
- e6c68fd1: Add stock-driven product auto-status sync
- 58f2c0e0: Implement SRS gaps: dashboard KPIs, lifecycle transitions, shipping APIs
- (working tree): Reviews moderation API + RBAC endpoints/tests
