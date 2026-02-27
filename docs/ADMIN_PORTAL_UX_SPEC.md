# Admin Portal UX Spec (Multi-tenant E-commerce SaaS)

## 1) Objective
Transform the admin portal from an internal utility interface into an executive-grade SaaS control center for platform operations, finance oversight, merchant performance, and risk governance.

Core outcomes:
- Executive visibility of platform health and growth
- Faster operational response to risk and payment failures
- Better merchant-level decision support
- Safer, clearer admin actions with permission-aware UX

---

## 2) Information Architecture

## 2.1 Primary Navigation
1. **Executive Overview**
2. **Merchants**
3. **Revenue**
4. **Risk & Fraud**
5. **Audit Trail**
6. **Operations**
7. **Permissions**
8. **Settings**

## 2.2 IA Principles
- Group by decision domain (performance, risk, governance), not by backend model names.
- Keep critical actions (suspend, payout approve, publish) one layer deep maximum.
- Surface cross-cutting status badges in nav (e.g., unresolved alerts count).

## 2.3 Cross-Module Entry Points
- Global search (merchant/store/order/admin action)
- Quick Actions drawer (right utility panel)
- Alerts center (critical first)

---

## 3) Executive Dashboard Layout Concept

## 3.1 Top KPI Strip (Priority)
Show 4 executive KPIs:
1. **Total Revenue**
2. **Active Stores**
3. **Failed Payments**
4. **Platform Growth**

Each card includes:
- Current value
- % change vs previous period
- Trend arrow and color
- Drilldown CTA

## 3.2 Main Grid (Desktop)
- **Left (8 cols):** Revenue trend visualization (weekly/monthly/quarterly)
- **Right (4 cols):** Merchant health summary + risk snapshot
- **Bottom Left:** Merchant health scorecards table/list
- **Bottom Right:** Fraud/risk alert queue + SLA timers
- **Bottom Full Width:** Audit timeline preview (latest privileged actions)

## 3.3 Right Utility Rail
- Quick actions:
  - Approve payouts
  - Suspend merchant
  - Re-verify KYC
  - Export compliance report
- Action safety hints and role requirements

## 3.4 Mobile/Tablet Behavior
- KPI cards stack in 2-column compact layout
- Charts become swipeable tabs
- Utility rail turns into bottom sheet
- Alert queue and audit timeline prioritized above dense tables

---

## 4) Merchant Health Scorecard View

## 4.1 Scorecard Dimensions
Per merchant/store:
- Revenue stability
- Payment success rate
- Fulfillment reliability
- Complaint/chargeback signals
- Subscription/payment timeliness

## 4.2 Health States
- **Healthy** (green)
- **Warning** (amber)
- **Critical** (red)

## 4.3 Scorecard Card Contents
- Composite health score (0–100)
- Top 3 risk drivers
- 7/30-day trend mini-chart
- Suggested action CTA (e.g., contact merchant, monitor, suspend review)

## 4.4 Bulk Monitoring
- Segment chips: Healthy / Warning / Critical
- Quick filter by account manager, region, plan tier, age

---

## 5) Risk/Fraud Alert Section

## 5.1 Alert Taxonomy
- Payment anomaly
- Velocity breach
- Geo/device mismatch
- High refund ratio
- Suspicious admin behavior

## 5.2 Alert Queue UX
- Sorted by severity + recency + SLA breach
- Alert item structure:
  - Severity badge
  - Alert title + reason
  - Affected merchant/store
  - Time since raised
  - Recommended next action

## 5.3 Case Workflow
States:
- New
- Investigating
- Escalated
- Resolved

Actions:
- Assign owner
- Add notes
- Attach evidence
- Resolve with reason

---

## 6) Visual Audit Activity Timeline

## 6.1 Timeline Event Card
- Actor (admin/system)
- Action type (create/update/delete/approve/suspend)
- Object target (merchant/store/payment/role)
- Timestamp
- Before/after diff preview
- Risk flag (if privileged/high-impact)

## 6.2 Timeline Views
- Chronological stream
- Group by actor
- Group by object type
- Export to CSV/PDF for compliance

## 6.3 Compliance Features
- Immutable event indicator
- Filter by privileged actions only
- Export with applied filters metadata

---

## 7) Advanced Filter UX Patterns

## 7.1 Filter Bar Pattern
- Primary filters visible by default
- “More filters” opens structured drawer
- Sticky apply/reset controls

## 7.2 Filter Types
- Date range presets + custom
- Multi-select tags
- Numeric ranges (revenue, failure rate)
- Status chips
- Boolean toggles (critical-only, unresolved-only)

## 7.3 Applied Filter UX
- Applied filter chips above table/list
- One-click remove per chip
- Clear all action
- Persist filter presets per admin user

---

## 8) Bulk Action UX Refinement

## 8.1 Selection Behavior
- Checkbox per row + select-all for current page + select all matching filter set
- Selection summary bar appears when >0 selected

## 8.2 Bulk Action Bar
- Contextual actions shown by current module + role
- Impact preview before execution
- Confirmation modal with explicit consequences

## 8.3 Post-action Feedback
- Partial success support (X succeeded, Y failed)
- Retry failed subset
- Download failure report

---

## 9) Modern SaaS Styling Direction

## 9.1 Theme Character
- Executive + operational clarity
- High density but readable
- Neutral foundations with semantic accents

## 9.2 Suggested Admin Theme Tokens
- Background: `#0B1220` / `#F8FAFC` (dark/light variants)
- Surface: `#111A2B` / `#FFFFFF`
- Primary accent: `#4F46E5`
- Info accent: `#06B6D4`
- Success: `#16A34A`
- Warning: `#F59E0B`
- Danger: `#DC2626`
- Text strong: `#E5E7EB` (dark) / `#0F172A` (light)
- Text muted: `#94A3B8` (dark) / `#64748B` (light)

## 9.3 Spacing & Hierarchy
- 8px spacing scale
- Card padding 16–20px
- Section gaps 24–32px
- One dominant CTA per section

---

## 10) Table Design with Search + Sort

## 10.1 Table Header
- Sticky header
- Sort controls on key columns
- Inline search with debounce
- Saved views presets

## 10.2 Row Design
- Clear row density modes (compact/comfortable)
- Context menu for row actions
- Inline status badges + trend indicators

## 10.3 Table States
- Loading skeleton
- Empty with contextual CTA
- Error with retry + support link

---

## 11) Permission Error UX (Friendly)

## 11.1 Replace Raw Errors with Guidance
Instead of generic 403:
- Title: **Action not available for your role**
- Message: **You need {{required_role}} to perform this action.**
- Actions:
  - **Request access**
  - **View allowed actions**
  - **Back to previous page**

## 11.2 Context-Aware Alternatives
- If action blocked, suggest nearest permitted action
- Preserve user context after permission escalation

## 11.3 Audit Integration
- Log denied attempts in audit timeline (with reason code)

---

## 12) UX Flow for Admin Operations

## 12.1 Executive Monitoring Flow
1. Land on Executive Overview
2. Scan KPI strip + trend deltas
3. Open critical alert or underperforming segment
4. Trigger quick action or assign investigation

## 12.2 Merchant Investigation Flow
1. Search merchant/store
2. Open health scorecard
3. Review risk drivers + payment history + recent audit actions
4. Execute guided action (monitor/escalate/suspend)

## 12.3 Fraud Response Flow
1. Enter Risk queue
2. Filter by severity + SLA breach
3. Review evidence and timeline
4. Assign case + set status + resolve reason

## 12.4 Governance & Compliance Flow
1. Open Audit Trail timeline
2. Filter by privileged action/date/actor
3. Inspect diffs for sensitive changes
4. Export report for compliance review

## 12.5 Bulk Operations Flow
1. Apply advanced filters
2. Select rows (current page or all filtered)
3. Review impact preview
4. Confirm action
5. Review outcome report

---

## 13) Microcopy Guidance

## KPI helper copy
- Total revenue: "Gross platform revenue for selected period."
- Failed payments: "Payments that did not complete successfully."

## Risk helper copy
- "Prioritize critical alerts to reduce platform exposure."

## Audit helper copy
- "Track who changed what and when across platform operations."

## Search placeholder
- "Search merchants, stores, payments, audits..."

---

## 14) Accessibility + Responsiveness
- Keyboard support for filters, tables, quick actions
- ARIA labels on charts and timeline events
- Contrast-compliant status colors
- Mobile-safe touch targets (≥44px)
- RTL-friendly layouts for Arabic support

---

## 15) Acceptance Criteria (UX)
1. Executive overview shows all four required KPIs with trends.
2. Merchant health scorecard exists with actionable health states.
3. Risk/fraud alert module supports severity-driven triage.
4. Audit timeline visualizes actor/action/object with time context.
5. Advanced filters support multi-dimensional narrowing with visible chips.
6. Bulk action UX includes selection summary, impact preview, and result summary.
7. Tables support search, sort, and consistent empty/loading/error states.
8. Permission failures are human-friendly with next-step guidance.
