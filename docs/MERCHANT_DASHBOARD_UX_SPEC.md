# Merchant Dashboard UX Spec (Multi-tenant Store Builder)

## 1) Objective
Redesign merchant dashboard UX to improve clarity, actionability, and mobile usability for daily store operations.

Primary goals:
- Prioritize business-critical KPIs
- Surface actionable alerts and guidance
- Reduce navigation and form friction
- Support mobile-first merchant behavior

---

## 2) Information Architecture

## Sidebar Navigation Groups
1. **Overview**
2. **Orders**
3. **Products**
4. **Customers**
5. **Marketing**
6. **Settings**

## Grouping Rules
- Keep max 6 top-level groups.
- Avoid mixing analytics actions with configuration actions.
- Keep destructive/admin-only actions inside Settings sub-sections.

---

## 3) Layout Blueprint

## Desktop (≥1024px)
- **Left Sidebar:** fixed; width 248px expanded / 80px collapsed
- **Top Bar:** global search, notifications, store switcher, user menu
- **Main Canvas:** 12-column responsive grid
- **Overview composition:**
  1. KPI strip (4 cards)
  2. Revenue chart area
  3. Operational widgets (pending shipments, recent orders)
  4. Onboarding checklist
  5. Smart notifications panel

## Tablet (768–1023px)
- Sidebar becomes collapsible drawer
- KPI cards in 2x2 grid
- Revenue chart full width
- Notifications and checklist stacked

## Mobile (<768px)
- Top app bar + search trigger
- Bottom navigation tabs: Overview, Orders, Products, More
- Sidebar content in slide-over sheet (More)
- KPI cards horizontal swipe or 2-column compact stack
- Sticky primary action button for key flows (e.g., Add Product)

---

## 4) Overview Screen Structure

## 4.1 KPI Priority Cards (Top row)
Cards (in order):
1. **Today Revenue**
2. **Orders**
3. **Conversion Rate**
4. **Pending Shipments**

Each card includes:
- Primary value
- Delta vs previous period
- Trend indicator (up/down/flat)
- Click target to drill-down page

## 4.2 Revenue Visualization
- Chart type: line/area chart
- Toggle: **Weekly / Monthly**
- Optional compare series: previous period
- Hover/tap tooltip values
- Empty chart fallback with setup CTA

## 4.3 Onboarding Checklist Widget
Suggested checklist items:
- Add first 5 products
- Configure payment method
- Set shipping rules
- Connect domain
- Launch first campaign

Behavior:
- Progress indicator (e.g., 3/5 completed)
- Completed items collapsed by default
- CTA button per item

## 4.4 Smart Notification Panel
Notification types:
- **Critical:** payment failures, sync errors
- **Warning:** low stock, delayed shipments
- **Info:** growth tips, feature recommendations

Each notification contains:
- Title
- Short context
- Suggested action CTA
- Timestamp

---

## 5) Empty State Patterns

## Orders Empty State
- Title: "No orders yet"
- Message: "Your orders will appear here once customers start purchasing."
- CTA: "Share your store" / "Run first campaign"

## Products Empty State
- Title: "Add your first product"
- Message: "Start with one product to make your store live-ready."
- CTA: "Add product"

## Revenue Empty State
- Title: "No revenue data yet"
- Message: "Revenue trends appear after your first completed order."
- CTA: "Review checkout settings"

## Customers Empty State
- Title: "No customers yet"
- Message: "Customers will appear after first checkout."
- CTA: "Invite visitors"

---

## 6) Form UX Structure (Long forms)
For long settings forms, use step-based sections:
- Section progress header
- 1 primary task per step
- Save-as-you-go behavior
- Sticky action footer on mobile

Example: Settings > Payments
1. Provider
2. Credentials
3. Webhooks
4. Test & confirm

---

## 7) Search & Command UX
Add global dashboard search with command-style behavior:
- Search entities: orders, products, customers, settings pages
- Keyboard shortcut (desktop): `/` or `Ctrl/Cmd + K`
- Recent searches + quick actions

Suggested quick actions:
- Add product
- Create discount
- View pending shipments
- Open payment settings

---

## 8) Notification UX Rules
- Unread badge on bell icon
- Critical alerts pinned at top until dismissed/resolved
- Batch similar alerts (e.g., low stock x 4 products)
- Keep max 5 visible at once with “View all”

---

## 9) Spacing + Button Hierarchy

## Spacing System
- 8px base scale
- Section gap: 24–32px desktop, 16–20px mobile
- Card internal spacing: 16–20px

## Button Hierarchy
- **Primary:** filled, one per section
- **Secondary:** outline for alternative path
- **Tertiary/Ghost:** low-emphasis actions
- Destructive actions must be isolated and labeled explicitly

---

## 10) UX Microcopy (Guidance)

## KPI tooltips
- Revenue: "Total paid order value for the selected period."
- Conversion: "Orders divided by storefront sessions."
- Pending shipments: "Orders paid but not yet dispatched."

## Checklist helper text
- "Complete these steps to unlock better conversion and store readiness."

## Smart alert helper text
- "Address critical alerts first to avoid order disruption."

## Search helper text
- Placeholder: "Search orders, products, customers, or settings..."

---

## 11) Component Breakdown

## Shell
- `DashboardShell`
- `SidebarNavigation`
- `TopBar`
- `MobileBottomNav`

## Data & Insight
- `KpiCard`
- `RevenueChartCard`
- `TrendBadge`
- `PendingShipmentsWidget`

## Guidance
- `OnboardingChecklist`
- `ChecklistItem`
- `ContextHelpPanel`
- `SmartNotificationPanel`

## Empty & Feedback
- `EmptyStateCard`
- `InlineHint`
- `Toast`
- `ErrorBanner`

## Interaction
- `GlobalSearchCommand`
- `QuickActionMenu`

---

## 12) UI Hierarchy Map
1. **Global Orientation**: sidebar + top bar + search
2. **Business Health**: KPI row
3. **Performance Trends**: revenue graph
4. **Action Queue**: pending shipments + notifications
5. **Guided Progress**: onboarding checklist
6. **Operational Details**: recent lists/tables

Rule: every screen should answer three questions in <5 seconds:
- What is happening now?
- What needs my action?
- What should I do next?

---

## 13) Accessibility & Responsiveness
- Touch targets ≥ 44px
- Contrast compliant text and controls
- Keyboard navigation for search and notifications
- Screen-reader labels for KPI cards and chart summaries
- RTL support for Arabic layouts

---

## 14) Screen-level Acceptance Criteria

## Navigation
- Sidebar contains only: Overview, Orders, Products, Customers, Marketing, Settings.
- Active state and section grouping are always visible.

## Overview
- Must show 4 KPI cards: Today Revenue, Orders, Conversion Rate, Pending Shipments.
- Must include weekly/monthly revenue visualization.
- Must include onboarding checklist widget.
- Must include smart notification panel.

## Empty states
- Empty states must provide clear next-step CTA (not blank placeholders).

## Mobile
- Dashboard is usable on 360px width without horizontal overflow.
- Primary actions remain accessible without deep scrolling.

---

## 15) Implementation Handoff Notes
- Keep design tokens consistent with existing system (no arbitrary new colors/shadows).
- Ensure cards and widgets can load independently (skeleton/loading states).
- Support tenant/store switch context in top bar.
- Log interactions for KPI clicks, checklist progress, notifications actions, and search usage.
