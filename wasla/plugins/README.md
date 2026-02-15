# Plugins Module | موديول الإضافات (Plugins)

**AR:** متجر الإضافات (App Store) بشكل مبسّط: تعريف الإضافة + تثبيتها لمتجر معين.  
**EN:** Simplified App Store: defines plugins and installs them per store.

---

## Key models | أهم الجداول

**AR/EN (see `apps/plugins/models.py`):**
- `Plugin`
- `InstalledPlugin` (per store)

---

## Services | الخدمات

**AR/EN:** `apps/plugins/services/` contains installation logic and basic operations.

---

## API | واجهة API

**AR/EN:** See `apps/plugins/urls.py` and `apps/plugins/views/api.py`.

