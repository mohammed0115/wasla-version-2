from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from django.conf import settings


class CredentialCrypto:
    """
    Vault-ready design:
    - Credentials are always encrypted at rest using a key derived from Django SECRET_KEY.
    - No email credentials are read from environment variables.
    """

    @staticmethod
    def encrypt_json(data: dict[str, Any]) -> str:
        raw = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        key = CredentialCrypto._derived_fernet_key()

        try:
            from cryptography.fernet import Fernet
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("cryptography is required for encrypted credentials.") from exc

        f = Fernet(key.encode("utf-8"))
        token = f.encrypt(raw)
        return "fernet:" + token.decode("ascii")

    @staticmethod
    def decrypt_json(token: str) -> dict[str, Any]:
        token = (token or "").strip()
        if not token:
            return {}

        if not token.startswith("fernet:"):
            raise RuntimeError("Unknown credentials encryption format.")

        key = CredentialCrypto._derived_fernet_key()

        try:
            from cryptography.fernet import Fernet
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("cryptography is required for encrypted credentials.") from exc

        f = Fernet(key.encode("utf-8"))
        raw = f.decrypt(token.removeprefix("fernet:").encode("ascii"))
        return json.loads(raw.decode("utf-8"))

    @staticmethod
    def _derived_fernet_key() -> str:
        """
        Derive a stable Fernet key from Django SECRET_KEY.
        This keeps provider credentials out of env files while still encrypting at rest.
        """
        secret = (getattr(settings, "SECRET_KEY", "") or "").encode("utf-8")
        if not secret:
            raise RuntimeError("SECRET_KEY is missing; cannot derive credentials encryption key.")
        digest = hashlib.sha256(secret + b"|emails.credentials.v1").digest()
        return base64.urlsafe_b64encode(digest).decode("ascii")

    @staticmethod
    def encrypt_text(value: str) -> str:
        raw = (value or "").encode("utf-8")
        if not raw:
            return ""
        key = CredentialCrypto._derived_fernet_key()
        try:
            from cryptography.fernet import Fernet
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("cryptography is required for encrypted credentials.") from exc
        f = Fernet(key.encode("utf-8"))
        token = f.encrypt(raw)
        return "fernet:" + token.decode("ascii")

    @staticmethod
    def decrypt_text(token: str) -> str:
        token = (token or "").strip()
        if not token:
            return ""
        if not token.startswith("fernet:"):
            raise RuntimeError("Unknown credentials encryption format.")
        key = CredentialCrypto._derived_fernet_key()
        try:
            from cryptography.fernet import Fernet
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("cryptography is required for encrypted credentials.") from exc
        f = Fernet(key.encode("utf-8"))
        raw = f.decrypt(token.removeprefix("fernet:").encode("ascii"))
        return raw.decode("utf-8")
