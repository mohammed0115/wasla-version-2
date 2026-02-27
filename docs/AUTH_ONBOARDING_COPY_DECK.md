# Auth & Onboarding Copy Deck

## Scope
Copy for authentication and onboarding journey of a multi-tenant e-commerce platform.
Tone: clear, confident, supportive, conversion-focused.

---

## 1) Auth Landing

## Hero
- Headline: **Start your store. Grow your brand.**
- Subheadline: **Launch in minutes with secure payments, guided setup, and everything you need to sell online.**
- Trust chips:
  - **SSL Secured**
  - **Trusted Payments**
  - **Always-on Platform**

## Primary CTA
- **Create your store**

## Secondary CTA
- **Log in**

## Footer helper
- **Need help? Contact support**

---

## 2) Login Tab

## Form labels
- Email or phone
- Password

## Placeholders
- Enter your email or phone
- Enter your password

## Actions
- Primary button: **Log in**
- Secondary text button: **Forgot password?**
- Optional link: **Use magic link instead**

## Validation
- Required: **This field is required.**
- Email/phone invalid: **Enter a valid email or phone number.**
- Password missing: **Enter your password.**

## Error states
- Invalid credentials: **Email/phone or password is incorrect.**
- Too many attempts: **Too many attempts. Please try again in a few minutes.**
- Generic: **Something went wrong. Please try again.**

## Loading state
- Button text: **Logging in...**

## Success
- Toast: **Welcome back! Redirecting to your dashboard...**

---

## 3) Register Tab

## Form labels
- Business email or phone
- Password
- Confirm password

## Placeholders
- Enter your business email or phone
- Create a password
- Confirm your password

## Helper text
- Password helper: **Use 8+ characters with upper/lowercase letters, numbers, and symbols.**

## Password strength labels
- **Weak**
- **Fair**
- **Good**
- **Strong**

## Actions
- Primary button: **Create my store**
- Secondary text: **Already have an account? Log in**

## Validation
- Required: **This field is required.**
- Email/phone invalid: **Enter a valid email or phone number.**
- Password weak: **Your password is too weak. Make it stronger to continue.**
- Confirm mismatch: **Passwords do not match.**

## Error states
- Existing account: **An account already exists with this email/phone. Log in instead.**
- Generic: **Couldn’t create your account. Please try again.**

## Loading state
- Button text: **Creating account...**

## Success
- Toast: **Account created successfully. Verify your code to continue.**

---

## 4) OTP Verification

## Page copy
- Title: **Verify your account**
- Subtitle: **Enter the 6-digit code sent to {{masked_destination}}**

## Actions
- Primary button: **Verify code**
- Secondary link: **Change email/phone**
- Resend default: **Resend code in {{seconds}}s**
- Resend active: **Didn’t get it? Resend code**

## Validation
- Incomplete code: **Enter the full 6-digit code.**
- Invalid code: **That code is incorrect. Try again.**
- Expired code: **This code has expired. Request a new one.**

## Loading
- Button text: **Verifying...**

## Success
- Toast: **Verified successfully. Let’s set up your store.**

---

## 5) Onboarding Wizard (Global)

## Persistent labels
- Step label: **Step {{current}} of 5**
- Progress label: **{{percent}}% complete**
- Back button: **Back**
- Continue button: **Continue**
- Skip button (where allowed): **Skip for now**

## Generic errors
- Save failed: **Couldn’t save your changes. Please try again.**
- Network issue: **Connection issue detected. Check your internet and retry.**

## Generic success
- Step saved: **Saved successfully.**

---

## 6) Step 1 — Create Store Name

## Copy
- Title: **Name your store**
- Subtitle: **Choose a name your customers will remember.**
- Field label: **Store name**
- Placeholder: **e.g., Noor Boutique**
- URL preview label: **Your store URL preview**

## Validation
- Required: **Store name is required.**
- Too short: **Store name must be at least 3 characters.**
- Invalid characters: **Use letters, numbers, spaces, or hyphens only.**
- Slug unavailable: **This store URL is already taken. Try another name.**

## Loading
- Saving button: **Saving...**

---

## 7) Step 2 — Upload Logo

## Copy
- Title: **Add your logo**
- Subtitle: **Upload your brand logo to personalize your storefront.**
- Dropzone default: **Drag & drop your logo here, or click to upload**
- Format helper: **PNG, JPG, or SVG up to 2MB**

## Actions
- Primary: **Upload & continue**
- Secondary: **Skip for now**
- Replace action: **Replace logo**
- Remove action: **Remove**

## Validation
- Unsupported format: **Unsupported file type. Please upload PNG, JPG, or SVG.**
- Too large: **File is too large. Maximum size is 2MB.**

## Success
- Inline success: **Logo uploaded successfully.**

---

## 8) Step 3 — Add First Product

## Copy
- Title: **Add your first product**
- Subtitle: **Create one product now. You can add more anytime.**
- Fields:
  - Product name
  - Price
  - Product image

## Placeholders
- Product name: **e.g., Classic Cotton T-Shirt**
- Price: **e.g., 99.00**

## Validation
- Product name required: **Product name is required.**
- Price required: **Price is required.**
- Price invalid: **Enter a valid price greater than 0.**

## Actions
- Primary: **Save product & continue**
- Secondary: **I’ll add products later**

## Loading
- Button: **Saving product...**

## Success
- Toast: **First product added. Great start!**

---

## 9) Step 4 — Setup Payment

## Copy
- Title: **Set up payments**
- Subtitle: **Connect a payment method so you can accept customer orders.**
- Trust note: **Your payment data is encrypted and securely stored.**

## Payment states
- Not connected: **Not connected**
- Pending review: **Pending verification**
- Connected: **Connected**

## Actions
- Primary: **Connect payment**
- Continue CTA (if already configured): **Continue to publish**

## Validation / errors
- Missing required details: **Please complete all required payment details.**
- Provider error: **Couldn’t connect payment provider. Please retry.**

## Loading
- Button: **Connecting...**

## Success
- Toast: **Payment setup completed.**

---

## 10) Step 5 — Publish

## Copy
- Title: **Publish your store**
- Subtitle: **Your store is ready. Go live and start selling.**
- Checklist intro: **Before publishing, confirm these items:**
  - Store name set
  - Logo added
  - First product added
  - Payment configured

## Actions
- Primary: **Publish store**
- Secondary: **Back to edit**

## Loading
- Button: **Publishing...**

## Success state
- Title: **Your store is live 🎉**
- Message: **Congratulations! Your store is now published and ready for customers.**
- Primary CTA: **Go to dashboard**
- Secondary CTA: **View storefront**

## Error state
- Message: **Publish failed. Please try again in a moment.**

---

## 11) System Feedback Library

## Inline success examples
- **Looks good.**
- **Saved.**

## Inline error examples
- **Please fix this field.**
- **This value is invalid.**

## Toasts
- Success: **Saved successfully.**
- Warning: **Your session will expire soon.**
- Error: **Action failed. Please try again.**

## Empty states
- Products: **No products yet. Add your first product to start selling.**
- Payments: **No payment method connected yet. Connect one to accept orders.**

---

## 12) CTA Style Guide (labels only)
- Use verb-first actions: **Create**, **Verify**, **Save**, **Connect**, **Publish**
- Keep primary CTAs 2–4 words
- Avoid ambiguous labels like “Submit” or “Done” where context-specific labels are clearer
