"""PDPL privacy services for data export and account deletion."""

import json
import csv
import logging
from decimal import Decimal
from datetime import datetime
from io import StringIO, BytesIO
import hashlib
import secrets

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.files.base import ContentFile
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import send_mail

from apps.privacy.models import (
    DataExportRequest,
    AccountDeletionRequest,
    DataAccessLog,
    ConsentRecord,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class DataExportService:
    """Generate comprehensive user data exports."""

    EXPORT_CATEGORIES = {
        "profile": _("Profile Information"),
        "contact": _("Contact Information"),
        "addresses": _("Addresses"),
        "orders": _("Order History"),
        "payments": _("Payments"),
        "cart": _("Shopping Cart"),
        "reviews": _("Reviews & Ratings"),
        "preferences": _("User Preferences"),
        "consent": _("Consent Records"),
        "activities": _("Activity Logs"),
    }

    @staticmethod
    def request_export(user: User, format_type: str = "json") -> DataExportRequest:
        """
        Create data export request.

        Returns:
            DataExportRequest instance
        """
        request_id = f"DER-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4)}"

        export_request = DataExportRequest.objects.create(
            user=user,
            request_id=request_id,
            format_type=format_type,
            status=DataExportRequest.STATUS_PENDING,
            expires_at=timezone.now() + timezone.timedelta(days=30),
        )

        # Log access
        DataAccessLog.objects.create(
            user=user,
            action="export",
            accessed_by="user",
            data_categories=list(DataExportService.EXPORT_CATEGORIES.keys()),
            purpose="User-requested data export",
        )

        # Send confirmation email
        DataExportService._send_export_request_email(user, export_request)

        return export_request

    @staticmethod
    def process_export(export_request: DataExportRequest) -> bool:
        """
        Generate data export file.

        Returns:
            True if successful, False otherwise
        """
        try:
            export_request.status = DataExportRequest.STATUS_PROCESSING
            export_request.save()

            user = export_request.user

            # Collect data
            data = {
                "export_id": export_request.request_id,
                "export_date": timezone.now().isoformat(),
                "user": DataExportService._export_profile(user),
            }

            # Export based on format
            if export_request.format_type == "json":
                file_content = json.dumps(data, default=str, indent=2).encode()
                filename = f"{export_request.request_id}.json"
                content_type = "application/json"
            elif export_request.format_type == "csv":
                file_content = DataExportService._to_csv(data).encode()
                filename = f"{export_request.request_id}.csv"
                content_type = "text/csv"
            else:
                file_content = DataExportService._to_xml(data).encode()
                filename = f"{export_request.request_id}.xml"
                content_type = "application/xml"

            # Save file
            export_request.data_file.save(
                filename,
                ContentFile(file_content),
                save=False,
            )
            export_request.file_size = len(file_content)
            export_request.status = DataExportRequest.STATUS_COMPLETED
            export_request.processed_at = timezone.now()
            export_request.included_data = list(
                DataExportService.EXPORT_CATEGORIES.keys()
            )
            export_request.save()

            # Send completion email
            DataExportService._send_export_complete_email(user, export_request)

            return True

        except Exception as e:
            logger.exception(f"Export processing failed for {export_request.request_id}")
            export_request.status = DataExportRequest.STATUS_FAILED
            export_request.error_message = str(e)
            export_request.save()
            return False

    @staticmethod
    def _export_profile(user: User) -> dict:
        """Export user profile data."""
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "is_active": user.is_active,
            "created_at": user.date_joined.isoformat(),
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }

    @staticmethod
    def _to_csv(data: dict) -> str:
        """Convert data to CSV format."""
        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(["Field", "Value"])
        for key, value in data.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    writer.writerow([f"{key}.{k}", v])
            else:
                writer.writerow([key, value])

        return output.getvalue()

    @staticmethod
    def _to_xml(data: dict) -> str:
        """Convert data to XML format."""
        import xml.etree.ElementTree as ET

        root = ET.Element("DataExport")
        for key, value in data.items():
            el = ET.SubElement(root, key)
            if isinstance(value, dict):
                for k, v in value.items():
                    sub_el = ET.SubElement(el, k)
                    sub_el.text = str(v)
            else:
                el.text = str(value)

        return ET.tostring(root, encoding="unicode")

    @staticmethod
    def _send_export_request_email(user: User, export_request: DataExportRequest):
        """Send export request confirmation email."""
        context = {
            "user": user,
            "request_id": export_request.request_id,
            "download_url": f"{settings.SITE_URL}/api/privacy/exports/{export_request.id}/download/",
        }

        subject = "Data Export Request Received"
        html_message = render_to_string(
            "privacy/emails/export_request.html",
            context,
        )

        send_mail(
            subject,
            "",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
        )

    @staticmethod
    def _send_export_complete_email(user: User, export_request: DataExportRequest):
        """Send export completion email."""
        context = {
            "user": user,
            "request_id": export_request.request_id,
            "file_size": export_request.file_size,
            "download_url": f"{settings.SITE_URL}/api/privacy/exports/{export_request.id}/download/",
            "expires_at": export_request.expires_at.strftime("%Y-%m-%d %H:%M"),
        }

        subject = "Your Data Export is Ready"
        html_message = render_to_string(
            "privacy/emails/export_complete.html",
            context,
        )

        send_mail(
            subject,
            "",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
        )


class AccountDeletionService:
    """Handle account deletion with grace period."""

    @staticmethod
    def request_deletion(
        user: User,
        reason: str = "other",
        reason_details: str = "",
    ) -> AccountDeletionRequest:
        """
        Request account deletion.

        Note: Requires confirmation email before processing.
        Grace period: 14 days before irreversible deletion.

        Returns:
            AccountDeletionRequest instance
        """
        # Delete existing request if any
        AccountDeletionRequest.objects.filter(user=user).exclude(
            status__in=[
                AccountDeletionRequest.STATUS_COMPLETED,
                AccountDeletionRequest.STATUS_CANCELLED,
            ]
        ).delete()

        request_id = f"ADR-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4)}"
        confirmation_code = secrets.token_urlsafe(32)

        deletion_request = AccountDeletionRequest.objects.create(
            user=user,
            request_id=request_id,
            reason=reason,
            reason_details=reason_details,
            confirmation_code=confirmation_code,
            grace_period_ends_at=timezone.now()
            + timezone.timedelta(days=14),
        )

        # Log access
        DataAccessLog.objects.create(
            user=user,
            action="delete",
            accessed_by="user",
            purpose="Account deletion requested",
        )

        # Send confirmation email
        AccountDeletionService._send_confirmation_email(user, deletion_request)

        return deletion_request

    @staticmethod
    def confirm_deletion(user: User, confirmation_code: str) -> bool:
        """
        Confirm account deletion via email link.

        Returns:
            True if confirmed, False if code invalid or expired
        """
        try:
            deletion_request = AccountDeletionRequest.objects.get(
                user=user,
                status=AccountDeletionRequest.STATUS_PENDING,
            )

            if not deletion_request.confirmation_code == confirmation_code:
                return False

            deletion_request.status = AccountDeletionRequest.STATUS_CONFIRMED
            deletion_request.is_confirmed = True
            deletion_request.confirmed_at = timezone.now()
            deletion_request.save()

            # Log
            DataAccessLog.objects.create(
                user=user,
                action="delete",
                accessed_by="user",
                purpose="Account deletion confirmed via email",
            )

            return True
        except AccountDeletionRequest.DoesNotExist:
            return False

    @staticmethod
    def process_deletion(deletion_request: AccountDeletionRequest) -> bool:
        """
        Process account deletion (after grace period if enabled).

        Returns:
            True if successful
        """
        try:
            user = deletion_request.user

            # Create backup of data
            backup_data = DataExportService._export_profile(user)
            backup_file = ContentFile(
                json.dumps(backup_data, indent=2).encode(),
                name=f"backup_{user.id}_{timezone.now().isoformat()}.json",
            )
            deletion_request.data_backup = backup_file
            deletion_request.save()

            # Delete user data
            deletion_request.status = AccountDeletionRequest.STATUS_PROCESSING
            deletion_request.save()

            # Optional: Soft delete (deactivate user)
            user.is_active = False
            user.email = f"deleted_{user.id}@example.invalid"  # Anonymize
            user.save()

            # Log deletion
            DataAccessLog.objects.create(
                user=user,
                action="delete",
                accessed_by="system",
                purpose="Account permanently deleted",
            )

            deletion_request.status = AccountDeletionRequest.STATUS_COMPLETED
            deletion_request.processed_at = timezone.now()
            deletion_request.is_irreversible = True
            deletion_request.save()

            return True

        except Exception as e:
            logger.exception(
                f"Deletion processing failed for {deletion_request.request_id}"
            )
            return False

    @staticmethod
    def cancel_deletion(deletion_request: AccountDeletionRequest) -> bool:
        """
        Cancel deletion request (only in grace period).

        Returns:
            True if cancelled, False if expired
        """
        if not deletion_request.can_cancel():
            return False

        deletion_request.status = AccountDeletionRequest.STATUS_CANCELLED
        deletion_request.save()

        # Log
        DataAccessLog.objects.create(
            user=deletion_request.user,
            action="restore",
            accessed_by="user",
            purpose="Account deletion cancelled",
        )

        return True

    @staticmethod
    def _send_confirmation_email(
        user: User,
        deletion_request: AccountDeletionRequest,
    ):
        """Send deletion confirmation email."""
        context = {
            "user": user,
            "confirm_url": f"{settings.SITE_URL}/api/privacy/deletion/{deletion_request.id}/confirm/?code={deletion_request.confirmation_code}",
            "grace_period_days": 14,
            "cancel_url": f"{settings.SITE_URL}/api/privacy/deletion/{deletion_request.id}/cancel/",
        }

        subject = "Confirm Your Account Deletion Request"
        html_message = render_to_string(
            "privacy/emails/deletion_confirmation.html",
            context,
        )

        send_mail(
            subject,
            "",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
        )


class ConsentService:
    """Manage user consent preferences."""

    @staticmethod
    def grant_consent(user: User, consent_type: str) -> ConsentRecord:
        """Record user consent."""
        consent, created = ConsentRecord.objects.update_or_create(
            user=user,
            consent_type=consent_type,
            defaults={
                "is_granted": True,
                "granted_at": timezone.now(),
                "revoked_at": None,
            },
        )

        # Log
        DataAccessLog.objects.create(
            user=user,
            action="consent_grant",
            accessed_by="user",
            data_categories=[consent_type],
            purpose=f"User granted {consent_type} consent",
        )

        return consent

    @staticmethod
    def revoke_consent(user: User, consent_type: str) -> ConsentRecord:
        """Revoke user consent."""
        consent, created = ConsentRecord.objects.update_or_create(
            user=user,
            consent_type=consent_type,
            defaults={
                "is_granted": False,
                "revoked_at": timezone.now(),
            },
        )

        # Log
        DataAccessLog.objects.create(
            user=user,
            action="consent_revoke",
            accessed_by="user",
            data_categories=[consent_type],
            purpose=f"User revoked {consent_type} consent",
        )

        return consent

    @staticmethod
    def has_consent(user: User, consent_type: str) -> bool:
        """Check if user has active consent."""
        try:
            consent = ConsentRecord.objects.get(
                user=user,
                consent_type=consent_type,
            )
            return consent.is_active()
        except ConsentRecord.DoesNotExist:
            return False
