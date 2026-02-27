# Admin Portal Implementation Checklist

## 1) Delivery Phases

## Phase 1 — Foundation & Navigation
- [ ] Implement admin shell layout (sidebar + topbar + content canvas)
- [ ] Add IA groups:
  - Executive Overview
  - Merchants
  - Revenue
  - Risk & Fraud
  - Audit Trail
  - Operations
  - Permissions
  - Settings
- [ ] Add global search shell (merchant/store/payment/audit)
- [ ] Add responsive behavior for desktop/tablet/mobile

## Phase 2 — Executive Overview
- [ ] Build KPI cards:
  - Total Revenue
  - Active Stores
  - Failed Payments
  - Platform Growth
- [ ] Build revenue visualization (weekly/monthly/quarterly)
- [ ] Add merchant health summary panel
- [ ] Add risk snapshot panel
- [ ] Add quick actions utility rail

## Phase 3 — Risk & Governance
- [ ] Build fraud/risk alert queue with severity and SLA timers
- [ ] Build case workflow actions (assign/escalate/resolve)
- [ ] Build audit timeline stream with actor/action/object context
- [ ] Add before/after diff preview in audit items

## Phase 4 — Operations UX
- [ ] Build advanced filter bar + filter drawer patterns
- [ ] Build search/sort table framework
- [ ] Build bulk action bar with impact preview
- [ ] Add bulk action result summary (success/partial/failure)

## Phase 5 — Permission UX + Hardening
- [ ] Replace raw permission errors with role-aware guidance states
- [ ] Add request-access CTA flow hook
- [ ] Log denied actions in audit trail
- [ ] Add accessibility + i18n/RTL pass

---

## 2) Component Build Checklist

## Shell & Navigation
- [ ] `AdminShell`
- [ ] `AdminSidebar`
- [ ] `AdminTopbar`
- [ ] `GlobalSearchCommand`
- [ ] `QuickActionsRail`

## Executive Widgets
- [ ] `ExecutiveKpiCard`
- [ ] `RevenueTrendChart`
- [ ] `GrowthDeltaBadge`
- [ ] `MerchantHealthSummary`
- [ ] `RiskSnapshotCard`

## Risk & Fraud
- [ ] `RiskAlertQueue`
- [ ] `RiskAlertItem`
- [ ] `CaseAssignmentControl`
- [ ] `CaseStatusStepper`

## Audit
- [ ] `AuditTimeline`
- [ ] `AuditEventCard`
- [ ] `AuditDiffPreview`
- [ ] `AuditExportControl`

## Table & Filters
- [ ] `AdvancedFilterBar`
- [ ] `FilterDrawer`
- [ ] `AppliedFilterChips`
- [ ] `AdminDataTable`
- [ ] `BulkActionBar`
- [ ] `BulkImpactModal`

## State & Feedback
- [ ] `EmptyStateCard`
- [ ] `SkeletonState`
- [ ] `InlineErrorBanner`
- [ ] `PermissionDeniedState`
- [ ] `ToastFeedback`

---

## 3) Data Contracts (Required)

## Executive KPIs
- total_revenue_amount
- total_revenue_delta_percent
- active_stores_count
- active_stores_delta_percent
- failed_payments_count
- failed_payments_delta_percent
- platform_growth_percent
- platform_growth_delta_percent

## Revenue Chart
- range (weekly/monthly/quarterly)
- labels[]
- current_values[]
- previous_values[] (optional)
- currency

## Merchant Health
- merchant_id
- merchant_name
- health_score (0–100)
- health_state (healthy/warning/critical)
- risk_drivers[]
- trend_7d
- trend_30d

## Risk Alerts
- alert_id
- severity (critical/warning/info)
- category
- merchant_id/store_id
- title
- description
- status (new/investigating/escalated/resolved)
- sla_due_at
- owner_id
- created_at

## Audit Events
- event_id
- actor
- action
- object_type
- object_id
- timestamp
- before_snapshot (optional)
- after_snapshot (optional)
- risk_flag (boolean)

---

## 4) Suggested Endpoint Map

## Executive Overview
- GET `/api/admin/overview/kpis`
- GET `/api/admin/overview/revenue?range=weekly|monthly|quarterly`
- GET `/api/admin/overview/merchant-health-summary`
- GET `/api/admin/overview/risk-snapshot`

## Merchants
- GET `/api/admin/merchants?filters...&sort...&search...`
- GET `/api/admin/merchants/{id}/health`
- POST `/api/admin/merchants/bulk-action`

## Risk & Fraud
- GET `/api/admin/risk/alerts?filters...`
- POST `/api/admin/risk/alerts/{id}/assign`
- POST `/api/admin/risk/alerts/{id}/status`

## Audit Trail
- GET `/api/admin/audit/events?filters...`
- GET `/api/admin/audit/events/{id}`
- GET `/api/admin/audit/export?filters...`

## Permissions
- POST `/api/admin/access/request`

---

## 5) UX State Matrix

Per widget/module:
- [ ] Loading state
- [ ] Success/data state
- [ ] Empty state with contextual CTA
- [ ] Error state with retry guidance

Per admin action:
- [ ] Idle
- [ ] In progress
- [ ] Completed
- [ ] Partial success
- [ ] Failed with resolution hint

Permission-protected actions:
- [ ] Friendly denied state
- [ ] Required role shown
- [ ] Request-access path shown

---

## 6) Advanced Filter UX Requirements
- [ ] Quick filters visible in-line
- [ ] Secondary filters in drawer
- [ ] Applied filter chips with remove actions
- [ ] Save/load filter presets
- [ ] Clear all filters action

---

## 7) Bulk Action UX Requirements
- [ ] Multi-select row model
- [ ] Select all (page) and select all (filtered)
- [ ] Impact preview before confirm
- [ ] Permission check before submit
- [ ] Result summary with retry for failed subset

---

## 8) Accessibility + i18n/RTL Checklist

## Accessibility
- [ ] Keyboard navigation for filters/tables/modals
- [ ] Focus-visible on all actionable controls
- [ ] Chart/text alternatives for screen readers
- [ ] Contrast compliance for all semantic statuses

## i18n/RTL
- [ ] No hardcoded UI copy in components
- [ ] Date/number/currency localized
- [ ] RTL-safe layout for table/filter/search UI
- [ ] Severity/status badges readable in both EN/AR

---

## 9) QA Scenario Matrix

## Executive Overview
- [ ] KPI values load correctly and match backend totals
- [ ] Revenue chart range switching works correctly
- [ ] Quick action executes and returns clear status

## Merchant Health
- [ ] Health score and state badges map correctly
- [ ] Segment filtering (healthy/warning/critical) works

## Risk & Fraud
- [ ] Critical alerts are prioritized and visible
- [ ] SLA breach indicators render accurately
- [ ] Case transitions enforce valid state rules

## Audit
- [ ] Timeline ordering by timestamp is correct
- [ ] Actor/action/object filters work together
- [ ] Diff preview renders accurate before/after values

## Permissions
- [ ] Unauthorized action shows friendly state (not raw 403)
- [ ] Request-access flow is reachable and functional

---

## 10) Release Readiness
- [ ] Feature flag strategy defined for rollout
- [ ] Event tracking dashboards for adoption and action rates
- [ ] Product/design QA sign-off on hierarchy and style
- [ ] Security/compliance sign-off for audit and permission UX
- [ ] Post-release monitoring plan for alert response times and admin efficiency
