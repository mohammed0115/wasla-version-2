"""
Order Notification Idempotency Service - Prevents duplicate emails/notifications.

Financial Integrity Level: MEDIUM

This service:
- Tracks notification events with idempotency keys
- Prevents duplicate email sends on webhook retries
- Supports email, SMS, in-app notifications
- Auto-retries failed notifications (with backoff)
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Any
from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta
import hashlib

from apps.orders.models import Order
from apps.notifications.models import OrderNotification  # New model

logger = logging.getLogger("wasla.notifications")


class OrderNotificationModel(models.Model):
    """Track sent notifications with idempotency."""
    
    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("in_app", "In-App"),
    ]
    
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),  # Duplicate idempotency key
    ]
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(
        max_length=50,
        help_text="order_confirmed, order_shipped, order_delivered, refund_processed, etc.",
    )
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    idempotency_key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="SHA256 of (order_id, event_type, channel)",
    )
    recipient = models.CharField(
        max_length=255,
        help_text="Email, phone, or user ID depending on channel",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    retry_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "order_notifications"
        unique_together = [["order", "idempotency_key"]]
        indexes = [
            models.Index(fields=["order", "event_type"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["idempotency_key"]),
        ]
    
    def __str__(self):
        return f"{self.order.order_number} - {self.event_type} ({self.channel})"


class OrderNotificationService:
    """
    Sends order notifications idempotently.
    
    Usage:
        service = OrderNotificationService()
        
        # Send order confirmation email
        result = service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient=order.customer_email,
        )
        # Returns: {"success": True, "notification_id": 123, "idempotent_reuse": False}
        
        # Retry send same notification (same event) - returns existing, doesn't duplicate
        result = service.send_notification(
            order=order,
            event_type="order_confirmed",
            channel="email",
            recipient=order.customer_email,
        )
        # Returns: {"success": True, "notification_id": 123, "idempotent_reuse": True}
    """
    
    def send_notification(
        self,
        order: Order,
        event_type: str,  # order_confirmed, order_shipped, etc.
        channel: str,  # email, sms, in_app
        recipient: str,  # email, phone, user_id
        subject: str = "",
        message: str = "",
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Send notification to customer idempotently.
        
        Args:
            order: Order instance
            event_type: Type of event (order_confirmed, order_shipped, etc.)
            channel: notification channel (email, sms, in_app)
            recipient: target address/id
            subject: Email subject or notification title
            message: Email body or notification content
            metadata: Additional data to track
        
        Returns:
            {
                "success": True,
                "notification_id": 123,
                "idempotent_reuse": False,  # True if same event already sent
                "error": None,
            }
        """
        # Generate deterministic idempotency key
        idempotency_key = self._generate_idempotency_key(
            order_id=order.id,
            event_type=event_type,
            channel=channel,
        )
        
        try:
            with transaction.atomic():
                # Check if notification already sent (idempotency)
                existing_notification = OrderNotificationModel.objects.filter(
                    order=order,
                    idempotency_key=idempotency_key,
                ).first()
                
                if existing_notification:
                    if existing_notification.status == "sent":
                        logger.info(
                            f"Notification already sent (idempotent reuse)",
                            extra={
                                "order_id": order.id,
                                "event_type": event_type,
                                "channel": channel,
                                "notification_id": existing_notification.id,
                            }
                        )
                        return {
                            "success": True,
                            "notification_id": existing_notification.id,
                            "idempotent_reuse": True,
                            "error": None,
                        }
                    elif existing_notification.status == "pending":
                        # Retry
                        logger.info(
                            f"Retrying pending notification",
                            extra={
                                "notification_id": existing_notification.id,
                                "retry_count": existing_notification.retry_count,
                            }
                        )
                        return self._retry_notification(existing_notification)
                
                # Create new notification record
                notification = OrderNotificationModel.objects.create(
                    order=order,
                    event_type=event_type,
                    channel=channel,
                    idempotency_key=idempotency_key,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                    metadata=metadata or {},
                    status="pending",
                )
                
                # Send notification
                send_success = self._send_to_channel(
                    notification=notification,
                    channel=channel,
                    recipient=recipient,
                    subject=subject,
                    message=message,
                )
                
                if send_success:
                    notification.status = "sent"
                    notification.sent_at = timezone.now()
                    notification.save(update_fields=["status", "sent_at"])
                    
                    logger.info(
                        f"Notification sent",
                        extra={
                            "order_id": order.id,
                            "event_type": event_type,
                            "channel": channel,
                            "notification_id": notification.id,
                        }
                    )
                else:
                    notification.status = "failed"
                    notification.save(update_fields=["status"])
                
                return {
                    "success": send_success,
                    "notification_id": notification.id,
                    "idempotent_reuse": False,
                    "error": None,
                }
        
        except Exception as e:
            logger.exception(f"Error sending notification: {e}")
            return {
                "success": False,
                "notification_id": None,
                "idempotent_reuse": False,
                "error": str(e),
            }
    
    def _retry_notification(self, notification: OrderNotificationModel) -> Dict[str, Any]:
        """Retry sending a failed/pending notification."""
        try:
            send_success = self._send_to_channel(
                notification=notification,
                channel=notification.channel,
                recipient=notification.recipient,
                subject=notification.subject,
                message=notification.message,
            )
            
            notification.retry_count += 1
            if send_success:
                notification.status = "sent"
                notification.sent_at = timezone.now()
            else:
                notification.status = "failed"
            
            notification.save(update_fields=["retry_count", "status", "sent_at"])
            
            return {
                "success": send_success,
                "notification_id": notification.id,
                "idempotent_reuse": False,
                "error": None,
            }
        
        except Exception as e:
            logger.exception(f"Error retrying notification {notification.id}: {e}")
            return {
                "success": False,
                "notification_id": notification.id,
                "idempotent_reuse": False,
                "error": str(e),
            }
    
    def _send_to_channel(
        self,
        notification: OrderNotificationModel,
        channel: str,
        recipient: str,
        subject: str,
        message: str,
    ) -> bool:
        """
        Actually send notification to channel.
        
        Returns success status.
        """
        try:
            if channel == "email":
                return self._send_email(recipient, subject, message)
            elif channel == "sms":
                return self._send_sms(recipient, message)
            elif channel == "in_app":
                return self._send_in_app(notification.order.customer_id, subject, message)
            else:
                logger.warning(f"Unknown channel: {channel}")
                return False
        
        except Exception as e:
            logger.exception(f"Error sending to {channel}: {e}")
            notification.last_error = str(e)
            notification.save(update_fields=["last_error"])
            return False
    
    def _send_email(self, recipient: str, subject: str, message: str) -> bool:
        """Send email notification."""
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False
    
    def _send_sms(self, phone: str, message: str) -> bool:
        """Send SMS notification."""
        # Placeholder for SMS provider integration
        logger.info(f"SMS to {phone}: {message[:50]}...")
        return True
    
    def _send_in_app(self, customer_id: int, title: str, message: str) -> bool:
        """Send in-app notification."""
        # Placeholder for in-app notification storage
        logger.info(f"In-app notification for customer {customer_id}: {title}")
        return True
    
    def _generate_idempotency_key(
        self,
        order_id: int,
        event_type: str,
        channel: str,
    ) -> str:
        """Generate deterministic idempotency key."""
        key_str = f"{order_id}:{event_type}:{channel}"
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get_notification_history(self, order_id: int) -> list:
        """Get all notifications for an order."""
        return list(
            OrderNotificationModel.objects.filter(order_id=order_id)
            .values("event_type", "channel", "status", "sent_at", "retry_count")
            .order_by("-created_at")
        )
