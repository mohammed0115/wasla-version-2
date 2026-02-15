# Subscriptions Module | موديول الاشتراكات (Subscriptions)

**AR:** خطط الاشتراك واشتراك المتجر (MVP) + سياسة مميزات (Features/Entitlements) للتفعيل/الإخفاء.  
**EN:** Subscription plans + store subscriptions (MVP) with feature/entitlement checks.

---

## Key models | أهم الجداول

**AR/EN (see `apps/subscriptions/models.py`):**
- `SubscriptionPlan` (features + limits)
- `StoreSubscription` (active/expired/cancelled per store)

---

## Services | الخدمات

**AR/EN:** `apps/subscriptions/services/`:
- `subscription_service.py`
- `entitlement_service.py`
- `feature_policy.py`

---

## API | واجهة API

**AR/EN:** See `apps/subscriptions/urls.py` and `apps/subscriptions/views/api.py`.

