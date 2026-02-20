
from decimal import Decimal
from django.db import transaction
from ..models import Wallet, WalletTransaction
from apps.stores.models import Store

class WalletService:

    @staticmethod
    def get_or_create_wallet(store_id, currency="USD", tenant_id=None):
        resolved_tenant_id = tenant_id
        if resolved_tenant_id is None:
            resolved_tenant_id = (
                Store.objects.filter(id=store_id)
                .values_list("tenant_id", flat=True)
                .first()
            )
        wallet, _ = Wallet.objects.get_or_create(
            tenant_id=resolved_tenant_id,
            store_id=store_id,
            defaults={"currency": currency}
        )
        return wallet

    @staticmethod
    @transaction.atomic
    def credit(wallet, amount: Decimal, reference: str):
        if amount <= 0:
            raise ValueError("Amount must be positive")

        WalletTransaction.objects.create(
            tenant_id=wallet.tenant_id or wallet.store_id,
            wallet=wallet,
            transaction_type="credit",
            amount=amount,
            reference=reference
        )

        wallet.balance += amount
        wallet.save(update_fields=["balance"])

    @staticmethod
    @transaction.atomic
    def debit(wallet, amount: Decimal, reference: str):
        if wallet.balance < amount:
            raise ValueError("Insufficient balance")

        WalletTransaction.objects.create(
            tenant_id=wallet.tenant_id or wallet.store_id,
            wallet=wallet,
            transaction_type="debit",
            amount=amount,
            reference=reference
        )

        wallet.balance -= amount
        wallet.save(update_fields=["balance"])
