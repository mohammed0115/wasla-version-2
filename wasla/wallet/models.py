"""
Wallet models (MVP).

AR:
- محفظة لكل متجر + معاملات credit/debit.
- هذا النموذج مبسّط وقد يحتاج لاحقًا لتطبيق Ledger كامل (Available/Pending…).

EN:
- A wallet per store with credit/debit transactions.
- This is a simplified model; it can be extended to a full ledger later.
"""

from django.db import models


class Wallet(models.Model):
    """Wallet per store."""

    store_id = models.IntegerField()
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="USD")
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"Store {self.store_id} ({self.currency})"


class WalletTransaction(models.Model):
    """Wallet ledger entry (credit/debit)."""

    TRANSACTION_TYPES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
    ]
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.wallet} - {self.transaction_type} {self.amount}"
