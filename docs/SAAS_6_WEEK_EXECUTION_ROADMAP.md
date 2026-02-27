# 6-Week SaaS UX Gap Closure Roadmap
## Mapped to Existing Plan + Cross-Platform Workstreams

## Scope and Mapping Rules
- Timeline: 6 weeks (3 sprints × 2 weeks)
- Primary anchor: `docs/ADMIN_PORTAL_SPRINT_PLAN.md`
- Purpose: close `P0` gaps first while preserving current implementation direction
- Execution model: one anchored admin stream + parallel platform streams

---

## 1) Week-by-Week Delivery Plan

## Weeks 1–2 (Sprint 1 Anchor)
### Anchor from existing plan (Admin)
- S1-01 Admin Shell + Navigation IA
- S1-02 Global Search Shell (UI only)
- S1-03 Executive KPI API
- S1-04 KPI Cards + Loading/Error States
- S1-05 Revenue Trend API
- S1-06 Revenue Chart Widget
- S1-07 Design QA Pass
- S1-08 QA Functional + Responsive Pass

### Parallel additions for gap closure
#### Auth & Onboarding (P0)
- AO-01: Onboarding milestone IA (account → verify → plan/payment → readiness)
- AO-02: OTP confidence patterns (resend, cooldown, inline validation feedback)
- AO-03: Time-to-first-value baseline instrumentation

#### Design System & State Contracts (P0)
- DS-01: Unified state specs for loading/empty/error/success
- DS-02: KPI card and chart behavior contract for reuse beyond admin

### Exit criteria
- Admin executive overview live (as Milestone A)
- Onboarding flow has measurable first-value baseline
- Shared state contract published and used by at least admin + onboarding

---

## Weeks 3–4 (Sprint 2 Anchor)
### Anchor from existing plan (Admin)
- S2-01 Merchant Health Summary API + UI
- S2-02 Risk Alert Queue API
- S2-03 Risk Alert Queue UI + Case Actions
- S2-04 Audit Timeline API
- S2-05 Audit Timeline UI
- S2-06 Advanced Filter Framework
- S2-07 Bulk Action UX
- S2-08 Friendly Permission Denied UX
- S2-09 QA Governance Regression

### Parallel additions for gap closure
#### Merchant Dashboard (P0)
- MD-01: Decision-priority KPI ordering and card semantics
- MD-02: Proactive empty states and “next best action” blocks
- MD-03: Mobile ergonomics pass for top 5 merchant operational tasks

#### UX Logic & Perceived Performance (P0)
- UXP-01: Skeleton/progressive loading standard in dashboard lists/widgets
- UXP-02: Optimistic UI for low-risk actions (tag/update/status)
- UXP-03: Async feedback standard (pending/success/fail with recovery)

### Exit criteria
- Risk + audit + bulk operations live (as Milestone B)
- Merchant dashboard tasks complete faster with lower decision friction
- Perceived performance standards applied to core merchant/admin interactions

---

## Weeks 5–6 (Sprint 3 Anchor)
### Anchor from existing plan (Admin)
- S3-01 Accessibility Compliance Pass
- S3-02 i18n + RTL Integration
- S3-03 Analytics Instrumentation
- S3-04 Performance Optimization
- S3-05 Final UAT + Release Prep

### Parallel additions for gap closure
#### Analytics & Experimentation (P0)
- EXP-01: Event taxonomy for onboarding, merchant decisions, admin governance
- EXP-02: A/B framework starter (hypothesis template + guardrail metrics)
- EXP-03: Weekly insight review ritual (measure → decision → iteration)

#### Storefront Conversion (P1)
- SF-01: Trust/reassurance pattern pack on product and checkout
- SF-02: Checkout error recovery and progress confidence pass

### Exit criteria
- Platform has instrumentation and experimentation operating cadence
- Accessibility/i18n/performance hardening complete for targeted surfaces
- Storefront conversion baseline improvements in place for next cycle

---

## 2) Gap-to-Roadmap Traceability

## Auth & Onboarding (P0)
- Covered in Weeks 1–2: AO-01, AO-02, AO-03
- KPI targets: onboarding completion ↑, time-to-first-value ↓

## Merchant Dashboard (P0)
- Covered in Weeks 3–4: MD-01, MD-02, MD-03
- KPI targets: WAU ↑, task completion time ↓

## Admin Portal (P0)
- Covered by existing Sprint 1/2/3 stories (S1-xx, S2-xx, S3-xx)
- KPI targets: risk-response time ↓, governance throughput ↑

## Design System Consistency (P0)
- Covered in Weeks 1–2 and enforced in Weeks 3–6: DS-01, DS-02
- KPI targets: UI defects ↓, implementation speed ↑

## UX Logic & Perceived Performance (P0)
- Covered in Weeks 3–4 and hardened in Weeks 5–6: UXP-01..03 + S3-04
- KPI targets: perceived latency complaints ↓, action confidence ↑

## Analytics & Experimentation (P0)
- Covered in Weeks 5–6: EXP-01..03 + S3-03
- KPI targets: experiment velocity ↑, decision cycle time ↓

## Storefront Experience (P1)
- Covered in Weeks 5–6: SF-01, SF-02
- KPI targets: checkout conversion ↑, abandonment ↓

---

## 3) Ownership Model
- Product Designer: DS-01/02, AO-01, MD-01/02, SF-01
- Frontend Engineer: AO-02, MD-03, UXP-01/02/03, SF-02, S1/S2/S3 FE stories
- Backend Engineer: AO-03, EXP-01, S1/S2/S3 BE stories
- QA Engineer: S1-08, S2-09, S3-01 support, cross-stream regression
- Product Manager: EXP-02/03 operating cadence, UAT/release governance

---

## 4) KPIs and Review Cadence
- Weekly cadence: Friday KPI review + Monday scope adjustment
- Core KPIs:
  - Onboarding completion rate
  - Median time-to-first-value
  - Merchant weekly active rate
  - Admin risk-response time
  - Checkout conversion rate
  - UX experiments launched per month

---

## 5) Risks and Mitigations
- Risk: parallel streams overload FE capacity
  - Mitigation: cap WIP by enforcing one P0 stream per role at a time
- Risk: instrumentation delays invalidate experiments
  - Mitigation: EXP-01 and S3-03 treated as release blockers
- Risk: inconsistent state patterns reappear
  - Mitigation: DS-01/02 contract gate in PR checklist

---

## 6) What Is Already Covered vs Newly Added

## Already covered in existing sprint plan
- Admin executive overview, governance workflows, hardening, i18n, analytics baseline

## Newly added by this roadmap
- Auth/onboarding P0 closure stream
- Merchant dashboard P0 closure stream
- Shared UX state contract stream
- Formal experimentation operating model
- Storefront conversion P1 bridge tasks
