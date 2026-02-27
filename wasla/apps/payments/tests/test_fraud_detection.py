"""Tests for fraud detection service"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import TestCase
from django.utils import timezone

from apps.payments.security.fraud_detection import FraudDetectionService
from apps.payments.models import PaymentIntent


class TestFraudDetectionService(TestCase):
    """Test fraud detection risk scoring and velocity checks"""

    def setUp(self):
        """Set up test data"""
        self.tenant_id = 12345
        self.order_id = 67890
        self.amount = Decimal("100.00")
        self.currency = "USD"

    def test_check_payment_risk_no_history(self):
        """Test risk scoring with no payment history"""
        result = FraudDetectionService.check_payment_risk(
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            amount=self.amount,
            currency=self.currency,
        )
        
        # Should have low risk with no history
        self.assertIsInstance(result["risk_score"], int)
        self.assertGreaterEqual(result["risk_score"], 0)
        self.assertLessEqual(result["risk_score"], 100)
        self.assertFalse(result["is_flagged"])
        self.assertIsInstance(result["checks"], dict)
        
    @patch("apps.payments.models.PaymentIntent.objects.filter")
    def test_velocity_check_within_limits(self, mock_filter):
        """Test velocity check with attempts within limit"""
        # Mock 2 recent attempts (below 5 limit)
        mock_queryset = mock_filter.return_value
        mock_queryset.count.return_value = 2
        
        result = FraudDetectionService.check_payment_risk(
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            amount=self.amount,
            currency=self.currency,
        )
        
        # Should not flag velocity
        velocity_check = result["checks"].get("velocity_check")
        self.assertIsNotNone(velocity_check)
        self.assertTrue(velocity_check.get("passed", False))
        
    @patch("apps.payments.models.PaymentIntent.objects.filter")
    def test_velocity_check_exceeds_limit(self, mock_filter):
        """Test velocity check with too many attempts"""
        # Mock 6 recent attempts (exceeds 5 limit)
        mock_queryset = mock_filter.return_value
        mock_queryset.count.return_value = 6
        
        result = FraudDetectionService.check_payment_risk(
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            amount=self.amount,
            currency=self.currency,
        )
        
        # Should flag velocity and increase risk score
        velocity_check = result["checks"].get("velocity_check")
        self.assertIsNotNone(velocity_check)
        self.assertFalse(velocity_check.get("passed", True))
        self.assertGreater(result["risk_score"], 20)
        
    def test_amount_check_normal_amount(self):
        """Test amount check with normal transaction amount"""
        normal_amount = Decimal("50.00")
        
        result = FraudDetectionService.check_payment_risk(
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            amount=normal_amount,
            currency=self.currency,
        )
        
        # Should not flag normal amount
        amount_check = result["checks"].get("amount_check")
        self.assertIsNotNone(amount_check)
        self.assertTrue(amount_check.get("passed", False))
        
    def test_amount_check_large_single_amount(self):
        """Test amount check with large single transaction"""
        large_amount = Decimal("15000.00")
        
        result = FraudDetectionService.check_payment_risk(
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            amount=large_amount,
            currency=self.currency,
        )
        
        # Should flag large amount
        amount_check = result["checks"].get("amount_check")
        self.assertIsNotNone(amount_check)
        self.assertFalse(amount_check.get("passed", True))
        self.assertGreater(result["risk_score"], 20)
        
    @patch("apps.payments.models.PaymentIntent.objects.filter")
    def test_amount_check_cumulative_exceeds_limit(self, mock_filter):
        """Test amount check with cumulative amount exceeding hourly limit"""
        # Mock queryset that returns high cumulative amount
        mock_queryset = mock_filter.return_value
        mock_queryset.aggregate.return_value = {"total": Decimal("12000.00")}
        
        result = FraudDetectionService.check_payment_risk(
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            amount=Decimal("100.00"),
            currency=self.currency,
        )
        
        # Should flag cumulative amount
        amount_check = result["checks"].get("amount_check")
        self.assertIsNotNone(amount_check)
        self.assertFalse(amount_check.get("passed", True))
        
    @patch("apps.payments.models.PaymentIntent.objects.filter")
    def test_frequency_check_normal_pattern(self, mock_filter):
        """Test frequency check with normal payment pattern"""
        # Mock 3 payments today (normal)
        mock_queryset = mock_filter.return_value
        mock_queryset.count.return_value = 3
        
        result = FraudDetectionService.check_payment_risk(
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            amount=self.amount,
            currency=self.currency,
        )
        
        # Should not flag frequency
        frequency_check = result["checks"].get("frequency_check")
        self.assertIsNotNone(frequency_check)
        self.assertTrue(frequency_check.get("passed", False))
        
    @patch("apps.payments.models.PaymentIntent.objects.filter")
    def test_frequency_check_excessive_pattern(self, mock_filter):
        """Test frequency check with excessive payment frequency"""
        # Mock 25 payments today (suspicious)
        mock_queryset = mock_filter.return_value
        mock_queryset.count.return_value = 25
        
        result = FraudDetectionService.check_payment_risk(
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            amount=self.amount,
            currency=self.currency,
        )
        
        # Should flag frequency
        frequency_check = result["checks"].get("frequency_check")
        self.assertIsNotNone(frequency_check)
        self.assertFalse(frequency_check.get("passed", True))
        self.assertGreater(result["risk_score"], 20)
        
    def test_should_block_payment_low_risk(self):
        """Test payment blocking decision with low risk score"""
        low_risk_score = 15
        
        should_block = FraudDetectionService.should_block_payment(low_risk_score)
        
        self.assertFalse(should_block)
        
    def test_should_block_payment_medium_risk(self):
        """Test payment blocking decision with medium risk score"""
        medium_risk_score = 55
        
        should_block = FraudDetectionService.should_block_payment(medium_risk_score)
        
        # Medium risk should not auto-block (manual review)
        self.assertFalse(should_block)
        
    def test_should_block_payment_high_risk(self):
        """Test payment blocking decision with high risk score"""
        high_risk_score = 85
        
        should_block = FraudDetectionService.should_block_payment(high_risk_score)
        
        # High risk should auto-block
        self.assertTrue(should_block)
        
    def test_risk_score_boundaries(self):
        """Test risk score stays within 0-100 boundaries"""
        # Generate many violations to test score cap
        with patch("apps.payments.models.PaymentIntent.objects.filter") as mock_filter:
            # Mock extreme conditions
            mock_queryset = mock_filter.return_value
            mock_queryset.count.return_value = 100  # Excessive attempts
            mock_queryset.aggregate.return_value = {"total": Decimal("50000.00")}
            
            result = FraudDetectionService.check_payment_risk(
                tenant_id=self.tenant_id,
                order_id=self.order_id,
                amount=Decimal("20000.00"),
                currency=self.currency,
            )
            
            # Risk score should be capped at 100
            self.assertLessEqual(result["risk_score"], 100)
            self.assertGreaterEqual(result["risk_score"], 0)
            
    def test_is_flagged_correlates_with_risk(self):
        """Test that is_flagged is True when risk score exceeds threshold"""
        with patch("apps.payments.models.PaymentIntent.objects.filter") as mock_filter:
            # Create high-risk scenario
            mock_queryset = mock_filter.return_value
            mock_queryset.count.return_value = 10
            mock_queryset.aggregate.return_value = {"total": Decimal("15000.00")}
            
            result = FraudDetectionService.check_payment_risk(
                tenant_id=self.tenant_id,
                order_id=self.order_id,
                amount=Decimal("12000.00"),
                currency=self.currency,
            )
            
            # High risk should set is_flagged
            if result["risk_score"] >= FraudDetectionService.RISK_THRESHOLD_MEDIUM:
                self.assertTrue(result["is_flagged"])
