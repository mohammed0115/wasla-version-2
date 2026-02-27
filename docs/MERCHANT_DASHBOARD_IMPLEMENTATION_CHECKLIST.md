# Merchant Dashboard Implementation Checklist

## 1) Delivery Plan (Phased)

## Phase 1 — Foundation
- [ ] Implement dashboard shell layout (sidebar, top bar, content area)
- [ ] Add grouped sidebar navigation:
  - Overview
  - Orders
  - Products
  - Customers
  - Marketing
  - Settings
- [ ] Add responsive behavior (desktop, tablet, mobile breakpoints)
- [ ] Add global dashboard search trigger and command palette shell

## Phase 2 — Overview Core Widgets
- [ ] Build KPI cards:
  - Today revenue
  - Orders
  - Conversion rate
  - Pending shipments
- [ ] Add KPI loading/skeleton states
- [ ] Add KPI error/fallback states
- [ ] Implement weekly/monthly revenue chart widget
- [ ] Add chart empty state with CTA

## Phase 3 — Guidance + Alerts
- [ ] Build onboarding checklist widget with progress state
- [ ] Build smart notification panel with severity levels
- [ ] Add empty state components for Orders/Products/Revenue/Customers
- [ ] Add contextual help panel patterns for key modules

## Phase 4 — Mobile Optimization
- [ ] Implement mobile top app bar
- [ ] Implement bottom nav (Overview, Orders, Products, More)
- [ ] Implement slide-over full navigation in More
- [ ] Verify sticky CTA patterns for mobile actions

## Phase 5 — Instrumentation + QA
- [ ] Add analytics events for KPI clicks, checklist actions, alerts actions, search usage
- [ ] Add accessibility audit pass (keyboard, ARIA, contrast)
- [ ] Add responsive QA matrix across target breakpoints
- [ ] Perform tenant-context isolation tests

---

## 2) Component Build Checklist

## Navigation & Shell
- [ ] DashboardShell
- [ ] SidebarNavigation
- [ ] SidebarGroup
- [ ] NavItem (with active/badge states)
- [ ] TopBar (search, notifications, switcher, profile)
- [ ] MobileBottomNav
- [ ] MobileSideSheet

## Data Widgets
- [ ] KpiCard
- [ ] RevenueChartCard
- [ ] PendingShipmentsWidget
- [ ] RecentOrdersWidget

## Guidance Widgets
- [ ] OnboardingChecklist
- [ ] ChecklistItem
- [ ] SmartNotificationPanel
- [ ] ContextHelpCard

## States & Feedback
- [ ] EmptyStateCard
- [ ] Skeleton loaders
- [ ] Inline warning/error banners
- [ ] Toast feedback

## Interaction
- [ ] GlobalSearchCommand
- [ ] QuickActionMenu

---

## 3) Data Contract Requirements

## KPI Cards (Overview)
Required fields:
- today_revenue_amount
- today_revenue_delta_percent
- orders_count
- orders_delta_percent
- conversion_rate_percent
- conversion_delta_percent
- pending_shipments_count
- pending_shipments_delta_percent

## Revenue Chart
Required fields:
- period_type (weekly/monthly)
- labels (array)
- current_period_values (array)
- previous_period_values (optional array)
- currency

## Onboarding Checklist
Required fields:
- items[]
  - id
  - title
  - description
  - status (pending/completed)
  - cta_label
  - cta_url
- completed_count
- total_count

## Notifications
Required fields:
- notifications[]
  - id
  - severity (critical/warning/info)
  - title
  - message
  - cta_label
  - cta_url
  - created_at
  - is_read

---

## 4) Suggested API Endpoints

## Overview Aggregates
- GET /api/dashboard/overview
  - returns KPI summary + pending shipments

## Revenue
- GET /api/dashboard/revenue?range=weekly
- GET /api/dashboard/revenue?range=monthly

## Onboarding
- GET /api/dashboard/onboarding-checklist
- POST /api/dashboard/onboarding-checklist/{item_id}/complete

## Notifications
- GET /api/dashboard/notifications
- POST /api/dashboard/notifications/{id}/read
- POST /api/dashboard/notifications/mark-all-read

## Search
- GET /api/dashboard/search?q={query}
  - returns mixed entities: orders, products, customers, routes

---

## 5) UX State Matrix (Must Implement)

Per widget:
- [ ] Loading state
- [ ] Success/data state
- [ ] Empty state with guidance CTA
- [ ] Error state with retry action

Per action:
- [ ] Idle
- [ ] In progress
- [ ] Success feedback
- [ ] Failure feedback

---

## 6) Multi-tenant Safety Checklist
- [ ] All dashboard queries scoped by active tenant/store context
- [ ] No cross-tenant search results
- [ ] Notifications are tenant-isolated
- [ ] KPI and chart responses validated against tenant/store ID

---

## 7) Accessibility & Internationalization

## Accessibility
- [ ] Keyboard focus order validated
- [ ] Focus-visible styles on all interactive controls
- [ ] Chart has text summary for screen readers
- [ ] Color contrast meets accessibility standards

## i18n/RTL
- [ ] All microcopy uses translation keys
- [ ] Sidebar and chart labels localized
- [ ] RTL alignment verified for Arabic
- [ ] Number/currency/date formatting localized

---

## 8) Performance Targets
- [ ] First meaningful dashboard render under agreed threshold
- [ ] KPI payload optimized (single aggregate call where possible)
- [ ] Chart data lazy loads if below-the-fold on mobile
- [ ] Notification polling/websocket strategy defined (if real-time)

---

## 9) QA Scenarios

## Core User Flows
- [ ] Merchant lands on Overview and immediately sees 4 KPI cards
- [ ] Merchant switches weekly/monthly chart and values update correctly
- [ ] Merchant completes checklist item and progress updates
- [ ] Merchant opens notification and executes CTA action
- [ ] Merchant uses global search to jump to order/product/customer/settings

## Empty States
- [ ] New merchant with no orders/products sees guided empty states
- [ ] Empty states show correct CTA per module

## Mobile
- [ ] No horizontal overflow on 360px width
- [ ] Bottom nav and More sheet work consistently
- [ ] Primary actions remain reachable without deep scroll

---

## 10) Release Readiness
- [ ] Feature flag strategy defined (if phased rollout)
- [ ] Analytics dashboard for new interactions prepared
- [ ] Product sign-off on UX acceptance criteria
- [ ] Design QA sign-off on spacing, hierarchy, and microcopy
- [ ] Post-release monitoring plan for engagement and task success
