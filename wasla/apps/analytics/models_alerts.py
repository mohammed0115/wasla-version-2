"""
Alert thresholds system for analytics dashboard.

Allows merchants and admins to set alerts for KPI thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from django.db import models
from django.utils import timezone


# ============================================================================
# Alert Models
# ============================================================================

class Alert(models.Model):
    """Alert threshold definition."""

    ALERT_TYPE_CHOICES = [
        ('low_stock', 'Low Stock Products'),
        ('low_conversion', 'Low Conversion Rate'),
        ('high_churn', 'High Churn Rate'),
        ('low_revenue', 'Low Revenue'),
        ('payment_failure', 'Payment Failures'),
        ('high_abandonment', 'High Cart Abandonment'),
        ('custom', 'Custom Metric'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    # For merchant alerts
    store_id = models.IntegerField(null=True, blank=True, db_index=True)
    
    # For admin alerts (platform-wide)
    is_admin = models.BooleanField(default=False, db_index=True)

    alert_type = models.CharField(max_length=50, choices=ALERT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Threshold values
    numeric_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    description = models.TextField(blank=True)

    # Notification settings
    notify_via_email = models.BooleanField(default=True)
    notify_via_dashboard = models.BooleanField(default=True)
    email_recipients = models.JSONField(default=list, blank=True)

    # Timing
    check_frequency = models.CharField(
        max_length=20,
        choices=[
            ('hourly', 'Hourly'),
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
        ],
        default='daily'
    )
    last_checked_at = models.DateTimeField(null=True, blank=True)
    triggered_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['store_id', 'status']),
            models.Index(fields=['is_admin', 'status']),
            models.Index(fields=['triggered_at']),
        ]

    def __str__(self) -> str:
        scope = f"Store {self.store_id}" if self.store_id else "Platform"
        return f"{self.get_alert_type_display()} ({scope})"

    def is_triggered(self, current_value: Decimal) -> bool:
        """Check if alert threshold is triggered."""
        if self.alert_type == 'low_stock':
            return current_value < self.numeric_value
        elif self.alert_type == 'low_conversion':
            return current_value < self.numeric_value
        elif self.alert_type == 'high_churn':
            return current_value > self.numeric_value
        elif self.alert_type == 'low_revenue':
            return current_value < self.numeric_value
        elif self.alert_type == 'payment_failure':
            return current_value > self.numeric_value
        elif self.alert_type == 'high_abandonment':
            return current_value > self.numeric_value
        return False


class AlertLog(models.Model):
    """Log of alert triggers and notifications."""

    ALERT_STATUS_CHOICES = [
        ('triggered', 'Triggered'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]

    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, related_name='logs')
    status = models.CharField(max_length=20, choices=ALERT_STATUS_CHOICES, default='triggered')

    current_value = models.DecimalField(max_digits=10, decimal_places=2)
    threshold_value = models.DecimalField(max_digits=10, decimal_places=2)

    triggered_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    notification_sent = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['alert_id', 'triggered_at']),
            models.Index(fields=['status', 'triggered_at']),
        ]
        ordering = ['-triggered_at']

    def __str__(self) -> str:
        return f"Alert: {self.alert.get_alert_type_display()} ({self.get_status_display()})"

    def acknowledge(self):
        """Mark alert as acknowledged."""
        self.status = 'acknowledged'
        self.acknowledged_at = timezone.now()
        self.save()

    def resolve(self):
        """Mark alert as resolved."""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save()


# ============================================================================
# Alert Service
# ============================================================================

class AlertService:
    """Service for managing and checking alerts."""

    @staticmethod
    def create_alert(
        store_id: int | None,
        alert_type: str,
        numeric_value: Decimal,
        is_admin: bool = False,
        description: str = '',
        notify_via_email: bool = True,
        check_frequency: str = 'daily'
    ) -> Alert:
        """
        Create a new alert.

        Args:
            store_id: Store ID (None for platform-wide)
            alert_type: Type of alert
            numeric_value: Threshold value
            is_admin: Whether this is admin alert
            description: Alert description
            notify_via_email: Send email notifications
            check_frequency: How often to check

        Returns:
            Alert object
        """
        alert = Alert.objects.create(
            store_id=store_id,
            alert_type=alert_type,
            numeric_value=numeric_value,
            is_admin=is_admin,
            description=description,
            notify_via_email=notify_via_email,
            check_frequency=check_frequency,
        )
        return alert

    @staticmethod
    def check_alert(alert: Alert, current_value: Decimal) -> AlertLog | None:
        """
        Check if alert should trigger.

        Args:
            alert: Alert to check
            current_value: Current metric value

        Returns:
            AlertLog if triggered, None otherwise
        """
        if alert.status != 'active':
            return None

        alert.last_checked_at = timezone.now()
        alert.save()

        # Check if triggered
        if not alert.is_triggered(current_value):
            return None

        # Check if already triggered recently
        recent_log = AlertLog.objects.filter(
            alert=alert,
            status__in=['triggered', 'acknowledged']
        ).order_by('-triggered_at').first()

        if recent_log:
            # Already triggered, don't create duplicate
            return None

        # Create log entry
        log = AlertLog.objects.create(
            alert=alert,
            current_value=current_value,
            threshold_value=alert.numeric_value,
        )

        alert.triggered_at = timezone.now()
        alert.save()

        return log

    @staticmethod
    def check_store_alerts(store_id: int) -> list[AlertLog]:
        """
        Check all alerts for a store.

        Args:
            store_id: Store ID

        Returns:
            List of triggered alerts
        """
        from apps.analytics.application.dashboard_services import (
            MerchantDashboardService, FunnelAnalysisService
        )

        alerts = Alert.objects.filter(store_id=store_id, status='active')
        triggered = []

        kpi = MerchantDashboardService.get_merchant_kpis(store_id)
        funnel = FunnelAnalysisService.get_conversion_funnel(store_id, days=7)

        for alert in alerts:
            if alert.alert_type == 'low_stock':
                current = Decimal(len(kpi.low_stock_products))
            elif alert.alert_type == 'low_conversion':
                current = Decimal(str(kpi.conversion_rate))
            elif alert.alert_type == 'high_abandonment':
                current = Decimal(str(kpi.cart_abandonment_rate))
            elif alert.alert_type == 'low_revenue':
                current = kpi.revenue_today
            else:
                continue

            log = AlertService.check_alert(alert, current)
            if log:
                triggered.append(log)

        return triggered

    @staticmethod
    def check_admin_alerts() -> list[AlertLog]:
        """
        Check all admin (platform-wide) alerts.

        Returns:
            List of triggered alerts
        """
        from apps.analytics.application.dashboard_services import AdminExecutiveDashboardService

        alerts = Alert.objects.filter(is_admin=True, status='active')
        triggered = []

        kpi = AdminExecutiveDashboardService.get_admin_kpis()

        for alert in alerts:
            if alert.alert_type == 'high_churn':
                current = Decimal(str(kpi.churn_rate))
            elif alert.alert_type == 'low_conversion':
                current = Decimal(str(kpi.conversion_rate))
            elif alert.alert_type == 'payment_failure':
                current = Decimal(str(100 - kpi.payment_success_rate))
            else:
                continue

            log = AlertService.check_alert(alert, current)
            if log:
                triggered.append(log)

        return triggered

    @staticmethod
    def get_active_alerts(store_id: int | None = None, is_admin: bool = False) -> list[Alert]:
        """Get all active alerts."""
        query = Alert.objects.filter(status='active')

        if is_admin:
            query = query.filter(is_admin=True)
        elif store_id:
            query = query.filter(store_id=store_id)

        return list(query.order_by('alert_type'))

    @staticmethod
    def acknowledge_alert(alert_log_id: int):
        """Acknowledge an alert."""
        log = AlertLog.objects.get(id=alert_log_id)
        log.acknowledge()

    @staticmethod
    def resolve_alert(alert_log_id: int):
        """Resolve an alert."""
        log = AlertLog.objects.get(id=alert_log_id)
        log.resolve()

    @staticmethod
    def disable_alert(alert_id: int):
        """Disable an alert."""
        alert = Alert.objects.get(id=alert_id)
        alert.status = 'inactive'
        alert.save()

    @staticmethod
    def get_pending_alerts(store_id: int | None = None) -> list[AlertLog]:
        """Get all pending (triggered/acknowledged) alerts."""
        query = AlertLog.objects.filter(
            status__in=['triggered', 'acknowledged']
        ).order_by('-triggered_at')

        if store_id:
            query = query.filter(alert__store_id=store_id)

        return list(query[:20])  # Latest 20
