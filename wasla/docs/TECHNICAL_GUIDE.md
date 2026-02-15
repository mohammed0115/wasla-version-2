# Wasla Platform — Technical Guide (V1)

هذه الوثيقة تُسهّل على أي مبرمج فهم المشروع بسرعة من Module إلى آخر، وتشغيله محليًا وعلى سيرفر (Gunicorn + Nginx).

---

## 1) Tech Stack

- Python 3.11+
- Django 5 + DRF
- SQLite (dev) / PostgreSQL (prod)
- Static UI: Templates + app.css (Tajawal)
- AI Visual Search:
  - MVP Embeddings (offline) + FAISS (vector index)
  - Optional CLIP (إذا فعّلته)

---

## 2) Project Layout

داخل مجلد المشروع `wasla/`:

- `config/`  
  إعدادات Django والـ `urls.py` (ربط كل تطبيقات الويب والـ API).

- `accounts/`  
  Auth + OTP + Persona Onboarding (سيناريو التسجيل مثل سلة).
  - Model: `Profile` مرتبط بـ `User`.
  - يحفظ بيانات التاجر أثناء الـ onboarding (country/legal/channel/categories).

- `tenants/`  
  Multi-tenant store entity:
  - Model: `Tenant` (يمثل المتجر)
  - Model: `TenantMembership` يربط المستخدم بالمتجر (Owner/Admin…)
  - Web: store setup wizard + custom domain routes

- `stores/`  
  Plans بسيطة (UI-centric) — يتم إنشاء الباقات افتراضيًا في أول تشغيل.

- `subscriptions/`  
  SubscriptionPlan + StoreSubscription (MVP)  
  في V1 نقوم بعمل mirror لخطة `stores.Plan` إلى `subscriptions.SubscriptionPlan` حسب billing cycle.

- `ai/`  
  Visual Search + Product description (MVP)
  - `ai/infrastructure/embeddings/`:
    - `image_embedder.py` (CLIP اختياري + fallback)
    - `image_features.py` (offline embeddings)
    - `vector_store_faiss.py` (FAISS index per store)

- بقية التطبيقات: `catalog`, `orders`, `payments`, `settlements`… (موجودة كبنية وقابلة للتوسعة)

---

## 3) Registration + Onboarding Scenario (Salla-like)

### Flow
1. `/auth/`  
   تبويب (إنشاء حساب / تسجيل الدخول)

2. `/auth/verify/`  
   OTP verification (بعد التسجيل)

3. Persona questions:
   - `/onboarding/welcome/`
   - `/onboarding/country/`
   - `/onboarding/legal/`
   - `/onboarding/existing/`
   - `/onboarding/channel/`
   - `/onboarding/category/`  (يدعم Sub-category للإلكترونيات)

4. Plans:
   - `/persona/plans/`

### DB Persistence (مهم)
- يتم حفظ بيانات الـ persona في: `accounts.Profile`
  - `country`, `legal_entity`, `has_existing_business`, `selling_channel`,
    `category_main`, `category_sub`

- عند اختيار الباقة في `/persona/plans/` يتم:
  1) حفظ `Profile.plan`  
  2) إنشاء `Tenant` + `TenantMembership(owner)` إن لم يوجد متجر للمستخدم  
  3) إنشاء `StoreSubscription` وربطها بـ `store_id = tenant.id` مع خطة مناسبة ومدة (شهري/سنوي)

بعدها يتم تحويل المستخدم إلى:
- `tenants:store_setup_start` → `/store/setup`

---

## 4) Visual Search (AI)

### Endpoints
- `POST /api/ai/index-products`
  - يبني Embeddings للمنتجات ويحدّث FAISS index
  - باراميترات:
    - `product_ids=1,2,3` (اختياري)
    - `force=true` (إعادة بناء)

- `POST /api/ai/visual-search`
  - form-data:
    - `image` (required)
    - `top_n` (12/24)
    - filters: `price_min`, `price_max`, `color`, `brightness`, `white_background`, `category`, `material`, `style`

### Storage
- FAISS index per store:
  - `MEDIA_ROOT/ai_indexes/store_<id>/index.faiss`
  - `MEDIA_ROOT/ai_indexes/store_<id>/ids.json`

---

## 5) تشغيل المشروع محليًا

### 1) إعداد البيئة
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) تشغيل migrations
```bash
python manage.py migrate
```

### 3) تشغيل السيرفر
```bash
python manage.py runserver 0.0.0.0:8000
```

### 4) صفحات مهمة للاختبار
- Auth: `http://localhost:8000/auth/`
- Onboarding: بعد التسجيل
- Plans: `http://localhost:8000/persona/plans/`
- Store setup: `http://localhost:8000/store/setup`
- Visual Search UI: `http://localhost:8000/dashboard/ai/visual-search`

---

## 6) تفعيل SMTP (Hostinger)

في `.env`:
- `EMAIL_HOST=smtp.hostinger.com`
- `EMAIL_HOST_USER=info@w-sala.com`
- `EMAIL_HOST_PASSWORD=***`
- `EMAIL_PORT=587`
- `EMAIL_USE_TLS=1`

---

## 7) Deployment (Nginx + Gunicorn)

### Gunicorn
```bash
pip install gunicorn
gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 3
```

### Nginx (مثال)
- proxy_pass إلى `127.0.0.1:8001`
- static:
  - `STATIC_ROOT` → `/var/www/wasla/static/`
- media:
  - `MEDIA_ROOT` → `/var/www/wasla/media/`

### Collectstatic
```bash
python manage.py collectstatic
```

---

## 8) Troubleshooting

- **404 في صفحات tenants**  
  تأكد أن `config/urls.py` يحتوي include لـ `tenants.urls` (موجود في هذا الإصدار).

- **StoreSubscription end_date required**  
  النظام يحسب end_date تلقائيًا (30 يوم شهري / 365 يوم سنوي).

- **FAISS غير موجود**  
  النظام يعمل fallback، لكن الأفضل تثبيت: `faiss-cpu`.

---

## 9) Where to extend next

- ربط المنتجات (`catalog`) بالـ Tenant فعليًا (store-scoped catalog)
- تحسين CLIP + Attributes extraction
- بناء Admin workflows للتفعيل/الإيقاف/التسويات


---

## Store Setup Wizard (Step-by-Step)

### الهدف
بعد إكمال سيناريو التسجيل واختيار الباقة (Persona/Plans)، يتم إنشاء/ربط:
- User + Profile
- Tenant (Store) + TenantMembership(owner)
- StoreProfile (wizard state)
- StoreSubscription (خطة الاشتراك)

ثم يتم تحويل التاجر تلقائيًا إلى **معالج إعداد المتجر**.

### روابط المعالج
- Step 1 (بيانات المتجر): `/store/setup/step-1`
- Step 2 (الدفع): `/store/setup/step-2`
- Step 3 (الشحن): `/store/setup/step-3`
- Step 4 (الإطلاق): `/store/setup/step-4`

> التقدم محفوظ داخل DB:
- `tenants.Tenant.setup_step`
- `tenants.StoreProfile.setup_step`
- `tenants.Tenant.setup_completed`

### كيف يتم تحديث الخطوات؟
- Step 1: عند حفظ بيانات المتجر يتم استدعاء:
  - `StoreSetupWizardUseCase.mark_step_done(step=1)`
- Step 2: عند حفظ الدفع:
  - `UpdatePaymentSettingsUseCase` (يعمل mark_step_done(step=2))
- Step 3: عند حفظ الشحن:
  - `UpdateShippingSettingsUseCase` (يعمل mark_step_done(step=3))
- Step 4: عند تفعيل المتجر:
  - `ActivateStoreUseCase` يقوم بـ `StoreSetupWizardUseCase.complete_setup()`

### واجهة المعالج
يوجد Header موحد + Progress bar داخل:
- `templates/web/store/_wizard_header.html`

---

## Visual Search UI (Dashboard)

### الصفحة
- `/dashboard/ai/visual-search`

### ماذا تعمل؟
- رفع صورة + تشغيل `/api/ai/visual-search`
- عرض `query_attributes`
- عرض نتائج 12/24 مع Skeleton loading و Load More
- زر بناء/تحديث الفهرس:
  - `/api/ai/index-products` (اختياري: force)

### تفعيل CLIP (اختياري)
ضع متغيرات البيئة:
```bash
export AI_USE_CLIP_EMBEDDINGS=1
export AI_USE_CLIP_CATEGORIES=1
export AI_USE_CLIP_MATERIALS=1
export AI_USE_CLIP_STYLES=1
export AI_FAISS_INDEX_TYPE=ivf
```

---

## تشغيل السيرفر (Local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

### حسابات البريد (SMTP)
في `.env`:
- `EMAIL_HOST=smtp.hostinger.com`
- `DEFAULT_FROM_EMAIL=info@w-sala.com`


---

## QA (Manual + Automated)

### 1) Admin QA Dashboard

- Path: `/admin/qa-dashboard/`
- Goal: one page to verify core linkage:
  - `User → Profile → Tenant → Membership → StoreProfile → Subscription → Wizard progress`

What you should see for a correct flow:
- Owner exists (email)
- Profile persona fields filled
- StoreProfile exists (setup_step updated)
- Subscription exists (plan + dates)

### 2) Automated tests (pytest)

We ship a smoke-test suite to validate critical flows:
- Persona onboarding + plans selection creates:
  - Profile.plan
  - Tenant + owner membership
  - StoreProfile
  - StoreSubscription
- Store setup wizard steps update StoreProfile.setup_step

Run:
```bash
pytest
```

Notes:
- Tests use Django test client with `force_login`.
- If you run into missing dependencies, ensure you installed `pytest` and `pytest-django` from `requirements.txt`.


## QA Dashboard (Admin)

Path: `/admin/qa-dashboard/`

This page summarizes the linkage between:
**User → Profile → Tenant → Membership → StoreProfile → Subscription → Wizard progress**

### Admin actions (per store)
- **Build/Update Index**: runs the store-scoped product embeddings indexing (same logic as `/api/ai/index-products`).
  - Use `force` if you want to rebuild embeddings even if the product image fingerprint hasn't changed.
- **Run KPI**: runs a lightweight Visual Search KPI sampling using the management command:
  - `python manage.py ai_kpi_visual_search --store-id <ID> --samples 10 --top-n 12`

Notes:
- These actions are admin-only and designed for demos/QA. They show a short result summary via Django admin messages.
- If CLIP is enabled on the server, KPI and indexing will use CLIP embeddings automatically; otherwise it will fallback to the offline embedder.


## Demo Data Seeding (Products + Images)

- Admin: Go to `/admin/qa-dashboard/` and click **Seed Demo Products** for a tenant.
- CLI:

```bash
python manage.py seed_demo_products --store-id 1 --count 24 --reset --with-inventory
```

This creates store-scoped categories and products with generated JPEG images under `MEDIA_ROOT/store_<id>/products/`.



## Demo Seeding (Realistic Products + Images) — V11

You can generate a demo catalog with controlled image attributes so Visual Search filters (color / brightness / white_background) work nicely.

### CLI
```bash
python manage.py seed_demo_products --store-id 1 --count 24 --reset --with-inventory --white-bg-ratio 0.7
```

- `--white-bg-ratio`: fraction of products generated on white background (default 0.65).

### Admin QA Dashboard
Use **Seed Demo Products** action to create demo items quickly, then run:
1) **Build/Update Index**
2) **Visual Search** (upload any query image)
3) **Run KPI**
