"""
Merchant 2FA (TOTP) models and services.

Implements:
1. TOTPSecret model: Stores encrypted secret per user
2. TOTPService: 
   - Generate secret + QR code
   - Verify OTP token
   - Enable/disable 2FA
   - Backup codes for account recovery
"""

import pyotp
import qrcode
from io import BytesIO
import base64
from typing import Tuple, List
from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.emails.application.services.crypto import CredentialCrypto
import logging

logger = logging.getLogger("wasla.auth")


class TOTPSecret(models.Model):
    """
    Stores TOTP secret for user 2FA.
    
    Fields:
    - user: FK to User
    - secret: Encrypted TOTP secret (baseline32 encoded)
    - is_active: Whether 2FA is enabled
    - verified_at: When 2FA was first verified
    - backup_codes: Encrypted backup codes (JSON list)
    - failed_attempts: Failed OTP attempts (rate limiting)
    - last_failed_at: Last failed OTP attempt
    - created_at, updated_at: Audit timestamps
    
    Security:
    - Backup codes for account recovery
    - Rate limiting (max 5 failed attempts)
    - Audit trail of verification
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="totp_secret"
    )
    
    secret = models.TextField(
        help_text="Base32-encoded TOTP secret (encrypted)"
    )
    
    is_active = models.BooleanField(
        default=False,
        help_text="Whether 2FA is enabled"
    )
    
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user verified 2FA setup"
    )
    
    backup_codes = models.TextField(
        help_text="JSON list of encrypted backup codes [consumed codes filtered out]"
    )
    
    failed_attempts = models.IntegerField(
        default=0,
        help_text="Failed OTP verification attempts"
    )
    
    last_failed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last failed OTP attempt timestamp"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "accounts_totp_secret"
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]
    
    def __str__(self):
        return f"TOTP for {self.user.email}"
    
    def verify_token(self, token: str) -> bool:
        """
        Verify TOTP token.
        
        Args:
            token: 6-digit TOTP code or backup code
        
        Returns:
            True if valid, False if invalid
            
        Side effects:
            - Increments failed_attempts on failure
            - Resets failed_attempts on success
            - Marks backup code as consumed
        
        Rate limiting:
            5 failed attempts → lock for 5 minutes
        """
        
        # Check rate limiting
        if self.failed_attempts >= 5:
            if timezone.now() - self.last_failed_at < timezone.timedelta(minutes=5):
                logger.warning(
                    f"TOTP rate limit exceeded for user {self.user.id}",
                    extra={"user_id": self.user.id}
                )
                return False
            else:
                # Reset after 5 minutes
                self.failed_attempts = 0
        
        # Try as TOTP token first
        secret_value = self._get_secret_value()
        if not secret_value:
            return False
        totp = pyotp.TOTP(secret_value)
        if totp.verify(token):
            self.failed_attempts = 0
            self.save(update_fields=["failed_attempts"])
            return True
        
        # Try as backup code
        if self._verify_backup_code(token):
            self.failed_attempts = 0
            self.save(update_fields=["failed_attempts", "backup_codes"])
            return True
        
        # Failed verification
        self.failed_attempts += 1
        self.last_failed_at = timezone.now()
        self.save(update_fields=["failed_attempts", "last_failed_at"])
        
        logger.warning(
            f"Invalid TOTP/backup code for user {self.user.id}",
            extra={"user_id": self.user.id, "attempt": self.failed_attempts}
        )
        
        return False
    
    def _verify_backup_code(self, code: str) -> bool:
        """
        Verify and consume backup code.
        
        Backup codes are one-time use. Consuming a code removes it from list.
        """
        import json
        
        codes = self._get_backup_codes_list()
        if codes is None:
            return False
        
        if code in codes:
            codes.remove(code)
            try:
                self.backup_codes = CredentialCrypto.encrypt_text(json.dumps(codes))
            except Exception:
                logger.error(
                    "Failed to encrypt updated backup codes",
                    extra={"user_id": self.user.id},
                )
                return False
            
            logger.info(
                f"Backup code consumed for user {self.user.id}",
                extra={"user_id": self.user.id, "codes_remaining": len(codes)}
            )
            
            return True
        
        return False

    def _get_secret_value(self) -> str:
        raw = (self.secret or "").strip()
        if not raw:
            return ""
        if raw.startswith("fernet:"):
            try:
                return CredentialCrypto.decrypt_text(raw)
            except Exception:
                logger.error(
                    "Failed to decrypt TOTP secret",
                    extra={"user_id": self.user.id},
                )
                return ""
        return raw

    def _get_backup_codes_list(self):
        import json
        raw = (self.backup_codes or "").strip()
        if not raw:
            return []
        if raw.startswith("fernet:"):
            try:
                raw = CredentialCrypto.decrypt_text(raw)
            except Exception:
                logger.error(
                    "Failed to decrypt backup codes",
                    extra={"user_id": self.user.id},
                )
                return None
        try:
            return json.loads(raw) or []
        except (json.JSONDecodeError, TypeError):
            return None
    
    def get_backup_codes_display(self) -> List[str]:
        """Get list of remaining backup codes (for display during setup)."""
        codes = self._get_backup_codes_list()
        return codes or []


class TOTPService:
    """Service for TOTP setup and verification."""
    
    @staticmethod
    def generate_secret_and_qr(user: User) -> Tuple[str, str]:
        """
        Generate TOTP secret and QR code.
        
        Args:
            user: User instance
        
        Returns:
            (secret, qr_code_data_uri)
            
        QR code is base64 data URI for embedding in HTML:
        <img src="data:image/png;base64,..." />
        
        Flow:
        1. Generate random secret (pyotp)
        2. Create QR code with provisioning URI
        3. Return secret + QR code data URI
        
        User must:
        1. Scan QR with authenticator app (Google Authenticator, Authy)
        2. Enter code to verify
        3. Save backup codes
        4. Enable 2FA
        """
        
        # Generate secret
        secret = pyotp.random_base32()
        
        # Create TOTP provisioning URI
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="Wasla"
        )
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 data URI
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
        qr_code_uri = f"data:image/png;base64,{img_str}"
        
        logger.debug(
            f"Generated TOTP secret for user {user.id}",
            extra={"user_id": user.id}
        )
        
        return secret, qr_code_uri
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """
        Generate one-time use backup codes.
        
        Args:
            count: Number of codes to generate (default 10)
        
        Returns:
            List of backup codes (e.g., ["ABC123XYZ", ...])
        
        User should:
        1. Save codes in secure place
        2. Use if authenticator app is lost
        
        Each code is one-time use only.
        """
        import secrets
        return [secrets.token_hex(4).upper() for _ in range(count)]
    
    @staticmethod
    @transaction.atomic
    def enable_2fa(user: User, secret: str, backup_codes: List[str]) -> TOTPSecret:
        """
        Enable 2FA for user.
        
        Args:
            user: User instance
            secret: TOTP secret to store
            backup_codes: List of backup codes
        
        Returns:
            TOTPSecret instance
        
        Atomic operation:
        - Create or update TOTPSecret
        - Store secret + backup codes
        - Set is_active = True
        - Audit log
        """
        import json
        
        totp_secret, created = TOTPSecret.objects.get_or_create(user=user)
        
        totp_secret.secret = CredentialCrypto.encrypt_text(secret)
        totp_secret.backup_codes = CredentialCrypto.encrypt_text(json.dumps(backup_codes))
        totp_secret.is_active = True
        totp_secret.verified_at = timezone.now()
        totp_secret.failed_attempts = 0
        
        totp_secret.save()
        
        logger.info(
            f"2FA enabled for user {user.id}",
            extra={
                "user_id": user.id,
                "email": user.email,
                "backup_codes": len(backup_codes)
            }
        )
        
        return totp_secret
    
    @staticmethod
    @transaction.atomic
    def disable_2fa(user: User) -> bool:
        """
        Disable 2FA for user.
        
        Args:
            user: User instance
        
        Returns:
            True if disabled, False if wasn't enabled
        """
        
        try:
            totp_secret = user.totp_secret
            totp_secret.is_active = False
            totp_secret.save(update_fields=["is_active"])
            
            logger.info(
                f"2FA disabled for user {user.id}",
                extra={"user_id": user.id}
            )
            
            return True
        except TOTPSecret.DoesNotExist:
            return False
    
    @staticmethod
    def get_backup_codes(user: User) -> List[str]:
        """Get list of remaining backup codes for user."""
        try:
            return user.totp_secret.get_backup_codes_display()
        except (TOTPSecret.DoesNotExist, AttributeError):
            return []
