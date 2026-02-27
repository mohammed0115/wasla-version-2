# Authentication & Onboarding UI Spec

## 1) Product Goal
Design a mobile-first authentication and onboarding journey for a multi-tenant e-commerce platform (Salla/Shopify style) that:
- Converts visitors into registered merchants
- Reduces onboarding abandonment
- Builds trust for business-critical setup (payments, publishing)
- Delivers clear guidance from sign-up to first store publish

---

## 2) UX Principles
- **Clarity first**: one primary action per screen
- **Progressive disclosure**: advanced options hidden behind secondary links
- **Confidence through feedback**: immediate validation, visible loading, explicit success/error outcomes
- **Trust by default**: security and reliability cues present at key moments
- **Mobile-first ergonomics**: thumb-friendly controls, sticky primary CTA, minimal typing friction

---

## 3) End-to-End UX Flow

## A. Entry / Auth Landing
1. User lands on Auth page
2. Sees brand hero + value proposition + trust indicators
3. Chooses either **Log in** or **Create account** tab

## B. Registration Flow
1. Enter business email/phone + password
2. Real-time validation and password strength feedback
3. Submit and show loading state
4. OTP verification (6-digit segmented)
5. On success, redirect to onboarding wizard step 1

## C. Login Flow
1. Enter email/phone + password
2. Inline validation before submit
3. Loading state on submit
4. Success toast + redirect to dashboard or last intended page
5. Optional fallback: forgot password / magic link

## D. Onboarding Wizard (Post-registration)
1. **Create Store Name**
2. **Upload Logo**
3. **Add First Product**
4. **Setup Payment**
5. **Publish**

Each step has:
- Top progress bar (Step X of 5)
- Single main task
- Back + Continue controls
- Clear completion signal before moving next

---

## 4) Screen-by-Screen Wireframe Structure

## 4.1 Auth Landing (Mobile)
- Header: logo, language switch
- Hero block:
  - Headline (value proposition)
  - Short supporting text
  - Trust chips (Secure platform, SSL, Trusted payments)
- Auth card:
  - Tabs: Log in | Create account
  - Form fields
  - Primary CTA
  - Secondary links (forgot password / terms)

## 4.2 Auth Landing (Desktop)
- Two-column layout:
  - Left: Hero + social proof + trust indicators
  - Right: Auth card
- Form card stays vertically centered; hero copy remains visible without scrolling on common laptop heights

## 4.3 OTP Verification
- Title + context text ("Enter the code sent to +966******23")
- 6 segmented input boxes with auto-advance
- Countdown timer + resend action
- Channel switch (email/SMS) where available
- Sticky primary CTA: Verify code
- Inline error for invalid/expired OTP

## 4.4 Onboarding Step 1 — Store Name
- Step title and helper copy
- Store name input
- Optional generated URL preview (e.g., mystore.wasla.com)
- Validation and availability check states

## 4.5 Onboarding Step 2 — Upload Logo
- Drag/drop + upload area
- Preview thumbnail after upload
- Supported formats and size guidance
- Skip option (secondary)

## 4.6 Onboarding Step 3 — Add First Product
- Minimal quick form:
  - Product name
  - Price
  - Image
- "Add details later" note
- Save & continue

## 4.7 Onboarding Step 4 — Setup Payment
- Payment provider cards/list
- Connect action
- Security reassurance text
- State labels: Not connected / Connected

## 4.8 Onboarding Step 5 — Publish
- Readiness checklist summary
- Primary CTA: Publish Store
- Success confirmation with next-step CTA (Go to Dashboard)

---

## 5) Component Hierarchy

## Shell Level
- `AuthLayout`
  - `BrandHero`
  - `TrustIndicatorRow`
  - `AuthCard`

- `OnboardingLayout`
  - `ProgressHeader`
  - `StepBody`
  - `StickyActionFooter`

## Form System
- `InputField`
  - label, helper, error, success
- `PasswordInput`
  - visibility toggle
  - strength meter
- `PhoneEmailInput`
- `OTPInputGroup` (6 cells)
- `UploadDropzone`
- `InlineAlert`
- `Toast`
- `LoadingButton`

## Feedback & Status
- `ProgressBar`
- `StatusChip` (Connected / Pending / Error)
- `SuccessState`
- `ErrorState`
- `EmptyState`

---

## 6) Content & Messaging (Copy Deck)

## 6.1 Hero Copy Options
- **Headline:** Build your online store in minutes.
- **Subtext:** From product upload to secure payments, launch faster with guided setup.
- **Primary CTA:** Create your store
- **Secondary CTA:** Log in

Alternative:
- **Headline:** Start selling today, not next month.
- **Subtext:** Everything you need to launch and manage a modern storefront.

## 6.2 Trust Copy
- "Bank-grade security"
- "SSL-secured storefronts"
- "Trusted payment integrations"

## 6.3 Validation & Feedback Copy
- Required field: "This field is required."
- Invalid email: "Enter a valid email address."
- Weak password: "Use at least 8 characters with upper, lower, number, and symbol."
- OTP invalid: "Code is incorrect. Try again."
- OTP expired: "Code expired. Request a new one."
- Success save: "Saved successfully."
- Blocking error: "Something went wrong. Please try again."

## 6.4 Onboarding Step Titles
1. "Name your store"
2. "Add your logo"
3. "Add your first product"
4. "Set up payments"
5. "Publish your store"

---

## 7) Validation, Error, Success System

## Inline Validation Rules
- Validate on blur + on submit
- For critical constraints (password, store slug), show real-time hints while typing
- Do not show red errors before user interaction

## Error Types
- **Field-level**: under specific input
- **Form-level**: top alert for API or submission failures
- **Global toast**: non-blocking outcomes

## Success Patterns
- Green check state for completed step
- Toast confirmation for async actions
- Final celebratory publish state (subtle animation only)

---

## 8) Micro-Interactions & Motion
- Input focus transition: 150ms ease-out
- Button hover/press feedback: 120–180ms
- OTP auto-focus + backspace to previous cell
- Progress bar animated fill between steps: 250ms
- Upload success pulse/check: 200ms
- Loading indicators:
  - Button spinner for form submissions
  - Skeleton placeholders for async-loaded provider lists

Motion guidance:
- Keep subtle and functional
- Avoid parallax/heavy motion in auth
- Respect reduced-motion preferences

---

## 9) Mobile-First Responsive Rules
- Base breakpoint behavior targets 360px–430px first
- Sticky bottom primary CTA in forms/wizard steps
- Input height min 44px
- Horizontal padding 16px mobile, 24px tablet, 32px desktop
- Desktop switches to two-column where beneficial, but wizard remains single-task centered
- Keep primary CTA visible without excessive scrolling

---

## 10) Visual System (Suggested)

## Color Tokens
- `primary-600`: #4F46E5
- `primary-700`: #4338CA
- `success-600`: #16A34A
- `warning-500`: #F59E0B
- `error-600`: #DC2626
- `neutral-900`: #0F172A
- `neutral-700`: #334155
- `neutral-500`: #64748B
- `neutral-200`: #E2E8F0
- `neutral-50`: #F8FAFC

Usage:
- Primary for CTA, active tabs, progress fill
- Success/error strictly for feedback states
- Neutral palette for surfaces and typography hierarchy

## Typography
- Family: Inter (fallback: system sans)
- H1: 32/40, 600
- H2: 24/32, 600
- H3: 20/28, 500
- Body: 16/24, 400
- Small: 14/20, 400
- Caption: 12/16, 400
- Button label: 16/24, 500

## Spacing & Radius
- 8px spacing scale
- Card radius 12–16px
- Input radius 10–12px
- Minimal shadow; rely on contrast and borders

---

## 11) CTA Strategy
- One dominant primary CTA per screen
- Verb-led labels:
  - "Create account"
  - "Verify code"
  - "Continue"
  - "Publish store"
- Secondary actions are text or ghost style and visually de-emphasized

---

## 12) Accessibility Requirements
- Color contrast compliant for all text and interactive states
- Full keyboard navigation for auth and wizard
- Focus states always visible
- Screen-reader labels for OTP cells and upload controls
- Error messages announced with ARIA live regions

---

## 13) Analytics & Success Metrics
Track funnel events:
- `auth_viewed`
- `register_started`
- `register_submitted`
- `otp_verified`
- `onboarding_step_completed` (step index)
- `payment_connected`
- `store_published`
- `onboarding_abandoned` (step index)

Primary KPIs:
- Registration completion rate
- OTP success rate
- Time-to-publish
- Step drop-off by stage

---

## 14) Handoff Checklist (Design → Engineering)
- Finalized mobile + desktop frames for all auth/onboarding states
- Component state matrix (default, focus, error, success, loading, disabled)
- Copy strings approved for EN/AR localization
- Interaction specs (timing/easing) documented
- Event tracking schema aligned with analytics
- QA acceptance criteria per step signed off

---

## 15) Acceptance Criteria (MVP)
1. Auth page includes hero messaging + trust indicators + clear login/register separation.
2. Registration includes password strength meter and structured OTP flow.
3. All forms show inline validation, loading states, and success/error feedback.
4. Post-registration onboarding is exactly 5 guided steps with visible progress bar.
5. Experience is mobile-first and responsive across common breakpoints.
6. Primary CTA is visually dominant on each screen.
7. Final publish success state confirms store launch and next navigation path.
