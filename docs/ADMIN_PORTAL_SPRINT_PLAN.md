# Admin Portal Sprint Plan (Execution-Ready)

## Planning Assumptions
- Sprint length: 2 weeks
- Team roles:
  - Product Designer (PD)
  - Frontend Engineer (FE)
  - Backend Engineer (BE)
  - QA Engineer (QA)
  - Product Manager (PM)
- Estimation scale: Story points (SP)
  - S = 2 SP
  - M = 5 SP
  - L = 8 SP

---

## Sprint 1 — Foundation + Executive Overview

## Goal
Deliver admin shell, navigation IA, executive KPI overview, and revenue chart MVP.

## Stories

### S1-01 Admin Shell + Navigation IA
- Description: Implement admin shell, sidebar groups, topbar, responsive container.
- Size: **L (8 SP)**
- Owner: **FE**
- Dependencies: None
- Acceptance:
  - Sidebar includes required groups
  - Responsive shell works on desktop/tablet/mobile

### S1-02 Global Search Shell (UI only)
- Description: Add top-level search entry, command palette scaffold, keyboard trigger.
- Size: **M (5 SP)**
- Owner: **FE**
- Dependencies: S1-01
- Acceptance:
  - Search opens with `/` and `Ctrl/Cmd+K`
  - Placeholder and empty states visible

### S1-03 Executive KPI API
- Description: Build backend aggregate endpoint for 4 KPI metrics.
- Size: **M (5 SP)**
- Owner: **BE**
- Dependencies: None
- Acceptance:
  - Endpoint returns Total Revenue, Active Stores, Failed Payments, Platform Growth
  - Tenant-safe and permission-safe responses

### S1-04 KPI Cards + Loading/Error States
- Description: Bind KPI API to cards with deltas and skeleton/error states.
- Size: **M (5 SP)**
- Owner: **FE**
- Dependencies: S1-03
- Acceptance:
  - Cards render value + delta + trend
  - Loading/error/empty states handled

### S1-05 Revenue Trend API (weekly/monthly/quarterly)
- Description: Build chart data endpoint with range parameter.
- Size: **M (5 SP)**
- Owner: **BE**
- Dependencies: None
- Acceptance:
  - Returns labels + current values (+ optional previous values)

### S1-06 Revenue Chart Widget
- Description: Implement chart with range toggles and tooltip.
- Size: **M (5 SP)**
- Owner: **FE**
- Dependencies: S1-05
- Acceptance:
  - Toggle works and chart re-renders per range
  - Empty state includes CTA

### S1-07 Design QA Pass (Sprint 1 scope)
- Description: Validate spacing, hierarchy, and component consistency.
- Size: **S (2 SP)**
- Owner: **PD**
- Dependencies: S1-01..S1-06
- Acceptance:
  - Sign-off checklist completed

### S1-08 QA Functional + Responsive Pass
- Description: Validate KPI/chart behavior and breakpoints.
- Size: **M (5 SP)**
- Owner: **QA**
- Dependencies: S1-01..S1-06
- Acceptance:
  - Test report with pass/fail and defects

**Sprint 1 total: 40 SP**

---

## Sprint 2 — Risk, Audit, Filters, Bulk Actions

## Goal
Deliver operational intelligence modules and governance workflows.

## Stories

### S2-01 Merchant Health Summary API + UI
- Description: Build merchant health summary endpoint and dashboard panel.
- Size: **L (8 SP)**
- Owner: **BE + FE**
- Dependencies: Sprint 1 shell complete
- Acceptance:
  - Health states: healthy/warning/critical
  - Risk drivers visible

### S2-02 Risk Alert Queue API
- Description: Build risk alerts endpoint with severity/status/SLA metadata.
- Size: **M (5 SP)**
- Owner: **BE**
- Dependencies: None
- Acceptance:
  - Returns sortable/filterable alert list

### S2-03 Risk Alert Queue UI + Case Actions
- Description: Build alert list UI + assign/escalate/resolve actions.
- Size: **L (8 SP)**
- Owner: **FE**
- Dependencies: S2-02
- Acceptance:
  - Critical alerts pinned
  - Case state transitions supported

### S2-04 Audit Timeline API
- Description: Build audit events API with filters and diff payload.
- Size: **M (5 SP)**
- Owner: **BE**
- Dependencies: None
- Acceptance:
  - Supports actor/action/object/date filters

### S2-05 Audit Timeline UI
- Description: Implement visual timeline with event cards and diff preview drawer.
- Size: **L (8 SP)**
- Owner: **FE**
- Dependencies: S2-04
- Acceptance:
  - Timeline renders in chronological order
  - Diff preview opens per event

### S2-06 Advanced Filter Framework
- Description: Implement filter bar, filter drawer, applied chips, clear-all.
- Size: **M (5 SP)**
- Owner: **FE**
- Dependencies: S2-03/S2-05 table/list modules
- Acceptance:
  - Multi-filter combinations work
  - Applied chips reflect active filters

### S2-07 Bulk Action UX (select + impact preview + result)
- Description: Add row selection, bulk action bar, confirmation and result summary.
- Size: **L (8 SP)**
- Owner: **FE + BE**
- Dependencies: S2-06
- Acceptance:
  - Supports partial success and retry failed subset

### S2-08 Friendly Permission Denied UX
- Description: Replace raw permission errors with guided role-aware state.
- Size: **M (5 SP)**
- Owner: **FE + BE**
- Dependencies: Shared auth/permission middleware hooks
- Acceptance:
  - Required role shown
  - Request-access CTA available

### S2-09 QA Governance Regression
- Description: Validate risk, audit, filters, bulk actions, permissions.
- Size: **M (5 SP)**
- Owner: **QA**
- Dependencies: S2-01..S2-08
- Acceptance:
  - Regression suite report and release recommendation

**Sprint 2 total: 57 SP**

---

## Sprint 3 — Hardening, Accessibility, i18n, Analytics

## Goal
Production hardening and operational readiness.

## Stories

### S3-01 Accessibility Compliance Pass
- Description: Keyboard navigation, ARIA, contrast, focus states.
- Size: **M (5 SP)**
- Owner: **FE + QA**
- Dependencies: Sprint 2 complete

### S3-02 i18n + RTL Integration
- Description: Externalize copy keys, ensure RTL-safe layouts.
- Size: **M (5 SP)**
- Owner: **FE**
- Dependencies: Sprint 2 complete

### S3-03 Analytics Instrumentation
- Description: Track KPI clicks, risk actions, filter usage, bulk actions.
- Size: **M (5 SP)**
- Owner: **FE + BE**
- Dependencies: Sprint 2 complete

### S3-04 Performance Optimization
- Description: API aggregation, payload trims, lazy loading, chart optimization.
- Size: **M (5 SP)**
- Owner: **BE + FE**
- Dependencies: Sprint 2 complete

### S3-05 Final UAT + Release Prep
- Description: UAT sign-off, docs, release checklist, rollout plan.
- Size: **S (2 SP)**
- Owner: **PM + QA + PD**
- Dependencies: S3-01..S3-04

**Sprint 3 total: 22 SP**

---

## Dependency Map (High-level)
- Shell/navigation must ship before most feature modules.
- KPI/Revenue APIs unblock overview widgets.
- Risk/Audit APIs unblock operational and governance screens.
- Filter framework should precede bulk actions.
- Permission UX depends on consistent error contract from backend.

---

## Risk Register
- **Data inconsistency risk:** KPI definitions differ across teams.
  - Mitigation: KPI contract review before Sprint 1 dev.
- **Performance risk:** Heavy overview queries.
  - Mitigation: pre-aggregated metrics + caching strategy.
- **Permission complexity risk:** multiple admin roles.
  - Mitigation: role matrix + denied-action contract.
- **Scope creep risk:** adding modules outside MVP.
  - Mitigation: lock sprint acceptance criteria.

---

## Definition of Done (per story)
- Feature implemented and merged
- Loading/empty/error states included
- Tenant and permission safety verified
- Analytics events added (if user-interactive)
- QA test case passed
- UX acceptance criteria met

---

## Release Milestones
- **Milestone A:** Executive Overview live (end Sprint 1)
- **Milestone B:** Risk + Audit + Bulk Ops live (end Sprint 2)
- **Milestone C:** Production-ready hardening complete (end Sprint 3)
