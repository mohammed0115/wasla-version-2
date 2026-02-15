# Notifications Module | موديول الإشعارات (Notifications)

**AR:** هذا الموديول يركز على إرسال إشعارات البريد/OTP (MVP) عبر بوابات قابلة للاستبدال.  
**EN:** This module focuses on email notifications/OTP (MVP) via swappable gateways.

---

## Structure | الهيكل

- `domain/`: ports + policies + errors
- `application/use_cases/`: request/verify OTP + send email
- `infrastructure/`: gateways (console/smtp) + routing

---

## Email gateway routing | توجيه بوابة البريد

**AR/EN:** `apps/notifications/infrastructure/router.py::EmailGatewayRouter` resolves the active provider using email config from `apps/emails`.

---

## Key model | أهم جدول

**AR/EN:** `apps/notifications/models.py::EmailOtp`

