
from decimal import Decimal
from django.db import transaction
from ..models import Wallet, WalletTransaction

class WalletService:

    @staticmethod
    def get_or_create_wallet(store_id, currency="USD"):
        wallet, _ = Wallet.objects.get_or_create(
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
            wallet=wallet,
            transaction_type="debit",
            amount=amount,
            reference=reference
        )

        wallet.balance -= amount
        wallet.save(update_fields=["balance"])
