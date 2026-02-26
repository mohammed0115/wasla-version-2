"""Fraud detection hooks and risk scoring for payment system."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.payments.models import PaymentIntent, PaymentAttempt


class FraudDetectionService:
    """Fraud detection and risk scoring for payments."""

    # Risk score thresholds
    RISK_LOW = 20
    RISK_MEDIUM = 50
    RISK_HIGH = 75
    RISK_THRESHOLD_MEDIUM = RISK_MEDIUM
    RISK_THRESHOLD_HIGH = RISK_HIGH

    # Velocity check limits
    VELOCITY_WINDOW_MINUTES = 60
    MAX_ATTEMPTS_PER_HOUR = 5
    MAX_AMOUNT_PER_HOUR = Decimal("10000.00")

    @classmethod
    def check_payment_risk(
        cls,
        *,
        tenant_id: int,
        order_id: int,
        amount: Decimal,
        currency: str,
    ) -> dict:
        """
        Run fraud checks on payment intent.
        
        Returns:
            {
                "risk_score": int (0-100),
                "is_flagged": bool,
                "checks": {
                    "velocity_check": {...},
                    "amount_check": {...},
                    ...
                }
            }
        """
        checks = {}
        risk_score = 0

        # Velocity check: count recent attempts
        velocity_result = cls._velocity_check(tenant_id=tenant_id, order_id=order_id)
        checks["velocity_check"] = velocity_result
        risk_score += velocity_result["risk_points"]

        # Amount check: flag unusually large amounts
        amount_result = cls._amount_check(amount=amount, tenant_id=tenant_id)
        checks["amount_check"] = amount_result
        risk_score += amount_result["risk_points"]

        # Frequency check: multiple orders in short time
        frequency_result = cls._frequency_check(tenant_id=tenant_id)
        checks["frequency_check"] = frequency_result
        risk_score += frequency_result["risk_points"]

        # Cap risk score at 100
        risk_score = min(risk_score, 100)

        is_flagged = risk_score >= cls.RISK_MEDIUM

        return {
            "risk_score": risk_score,
            "is_flagged": is_flagged,
            "checks": checks,
        }

    @classmethod
    def _velocity_check(cls, *, tenant_id: int, order_id: int) -> dict:
        """Check if too many payment attempts in recent window."""
        since = timezone.now() - timedelta(minutes=cls.VELOCITY_WINDOW_MINUTES)
        
        recent_count = PaymentIntent.objects.filter(
            tenant_id=tenant_id,
            order_id=order_id,
            created_at__gte=since,
        ).count()
        if not isinstance(recent_count, int):
            try:
                recent_count = int(recent_count)
            except Exception:
                recent_count = 0

        risk_points = 0
        if recent_count >= cls.MAX_ATTEMPTS_PER_HOUR:
            risk_points = 40
        elif recent_count >= 3:
            risk_points = 20

        return {
            "recent_attempts": recent_count,
            "threshold": cls.MAX_ATTEMPTS_PER_HOUR,
            "window_minutes": cls.VELOCITY_WINDOW_MINUTES,
            "risk_points": risk_points,
            "passed": recent_count < cls.MAX_ATTEMPTS_PER_HOUR,
        }

    @classmethod
    def _amount_check(cls, *, amount: Decimal, tenant_id: int) -> dict:
        """Flag unusually large payment amounts."""
        since = timezone.now() - timedelta(minutes=cls.VELOCITY_WINDOW_MINUTES)
        
        recent_total = PaymentIntent.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=since,
        ).aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0")
        if not isinstance(recent_total, Decimal):
            try:
                recent_total = Decimal(str(recent_total))
            except Exception:
                recent_total = Decimal("0")

        risk_points = 0
        amount_breached = False
        
        # Single large amount
        if amount > Decimal("5000.00"):
            risk_points += 25
            amount_breached = True
        elif amount > Decimal("2000.00"):
            risk_points += 5

        # High total in window
        if recent_total > cls.MAX_AMOUNT_PER_HOUR:
            risk_points += 30
            amount_breached = True

        return {
            "amount": str(amount),
            "recent_total": str(recent_total),
            "threshold": str(cls.MAX_AMOUNT_PER_HOUR),
            "risk_points": risk_points,
            "passed": not amount_breached,
        }

    @classmethod
    def _frequency_check(cls, *, tenant_id: int) -> dict:
        """Check payment frequency patterns."""
        since = timezone.now() - timedelta(hours=24)
        
        daily_count = PaymentIntent.objects.filter(
            tenant_id=tenant_id,
            created_at__gte=since,
        ).count()
        if not isinstance(daily_count, int):
            try:
                daily_count = int(daily_count)
            except Exception:
                daily_count = 0

        risk_points = 0
        if daily_count > 50:
            risk_points = 40
        elif daily_count > 20:
            risk_points = 25

        return {
            "daily_count": daily_count,
            "risk_points": risk_points,
            "passed": daily_count <= 20,
        }

    @classmethod
    def should_block_payment(cls, risk_score: int) -> bool:
        """Determine if payment should be blocked based on risk score."""
        return risk_score >= cls.RISK_HIGH


# Import models after class definition to avoid circular import
from django.db import models
