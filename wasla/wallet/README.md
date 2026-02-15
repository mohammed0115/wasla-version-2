# Wallet Module | موديول المحفظة (Wallet)

**AR:** محفظة المتجر (رصيد + معاملات credit/debit) بشكل مبسط (MVP).  
**EN:** Store wallet (balance + credit/debit transactions) in a simplified MVP form.

---

## Key models | أهم الجداول

**AR/EN (see `apps/wallet/models.py`):**
- `Wallet` (per store)
- `WalletTransaction` (credit/debit entries)

---

## Services | الخدمات

**AR/EN:** `apps/wallet/services/wallet_service.py` contains basic operations for credit/debit.

---

## API | واجهة API

**AR/EN:** See `apps/wallet/urls.py` and `apps/wallet/views/api.py`.

