from __future__ import annotations

import os
import shutil
import ssl
import tempfile
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.domains.infrastructure.nginx_generator import NginxConfigGenerator
from apps.domains.infrastructure.ssl_manager import DomainSslManager


class SslRenewalService:
	RECENT_RENEWAL_WINDOW = timedelta(hours=24)

	def __init__(self, store_domain):
		self.store_domain = store_domain

	def is_recently_renewed(self) -> bool:
		health = getattr(self.store_domain, "health_status", None)
		if not health or not health.last_checked_at:
			return False
		if not health.ssl_expires_at:
			return False
		if (timezone.now() - health.last_checked_at) > self.RECENT_RENEWAL_WINDOW:
			return False
		return health.days_until_expiry is not None and health.days_until_expiry > 30

	def renew(self) -> dict:
		domain = self.store_domain.domain
		started_at = timezone.now()

		backup_cert = None
		backup_key = None
		temp_cert = None
		temp_key = None
		cert_destination = self.store_domain.ssl_cert_path or ""
		key_destination = self.store_domain.ssl_key_path or ""

		try:
			if not getattr(settings, "CUSTOM_DOMAIN_SSL_ENABLED", False):
				return {"success": False, "error": "SSL provisioning is disabled"}

			issued = DomainSslManager.issue(domain, renew=True)

			cert_source = issued.cert_path
			key_source = issued.key_path

			backup_cert, backup_key = self._backup_existing_files(cert_destination, key_destination)
			temp_cert, temp_key = self._copy_to_temp_for_validation(cert_source, key_source)
			self._validate_certificate_file(temp_cert)

			cert_final, key_final = self._atomic_activate_certificate(
				cert_source=cert_source,
				key_source=key_source,
				cert_destination=cert_destination,
				key_destination=key_destination,
			)

			self._regenerate_nginx(domain=domain, cert_path=cert_final, key_path=key_final)

			return {
				"success": True,
				"cert_path": cert_final,
				"key_path": key_final,
				"duration_ms": int((timezone.now() - started_at).total_seconds() * 1000),
			}

		except Exception as exc:
			self._rollback_certificate(cert_destination, key_destination, backup_cert, backup_key)
			return {
				"success": False,
				"error": str(exc),
				"duration_ms": int((timezone.now() - started_at).total_seconds() * 1000),
			}
		finally:
			self._safe_unlink(temp_cert)
			self._safe_unlink(temp_key)
			self._safe_unlink(backup_cert)
			self._safe_unlink(backup_key)

	def _backup_existing_files(self, cert_path: str, key_path: str):
		cert_backup = self._create_backup(cert_path)
		key_backup = self._create_backup(key_path)
		return cert_backup, key_backup

	def _copy_to_temp_for_validation(self, cert_path: str, key_path: str):
		cert_suffix = Path(cert_path).suffix or ".pem"
		key_suffix = Path(key_path).suffix or ".pem"

		cert_fd, temp_cert_path = tempfile.mkstemp(prefix="wasla-cert-", suffix=cert_suffix)
		key_fd, temp_key_path = tempfile.mkstemp(prefix="wasla-key-", suffix=key_suffix)
		os.close(cert_fd)
		os.close(key_fd)

		shutil.copy2(cert_path, temp_cert_path)
		shutil.copy2(key_path, temp_key_path)

		return temp_cert_path, temp_key_path

	def _validate_certificate_file(self, cert_path: str) -> None:
		decoded = ssl._ssl._test_decode_cert(cert_path)
		not_after = decoded.get("notAfter")
		if not not_after:
			raise RuntimeError("Renewed certificate has no expiry date")

		expires_at = timezone.make_aware(
			datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
		)
		if expires_at <= timezone.now():
			raise RuntimeError("Renewed certificate is already expired")

	def _atomic_activate_certificate(
		self,
		*,
		cert_source: str,
		key_source: str,
		cert_destination: str,
		key_destination: str,
	):
		if not cert_destination or not key_destination:
			return cert_source, key_source

		cert_destination_path = Path(cert_destination)
		key_destination_path = Path(key_destination)

		cert_destination_path.parent.mkdir(parents=True, exist_ok=True)
		key_destination_path.parent.mkdir(parents=True, exist_ok=True)

		cert_tmp = cert_destination_path.with_suffix(cert_destination_path.suffix + ".tmp")
		key_tmp = key_destination_path.with_suffix(key_destination_path.suffix + ".tmp")

		shutil.copy2(cert_source, cert_tmp)
		shutil.copy2(key_source, key_tmp)

		cert_tmp.replace(cert_destination_path)
		key_tmp.replace(key_destination_path)

		return str(cert_destination_path), str(key_destination_path)

	def _regenerate_nginx(self, *, domain: str, cert_path: str, key_path: str) -> None:
		if not getattr(settings, "CUSTOM_DOMAIN_NGINX_ENABLED", False):
			return

		generator = NginxConfigGenerator()
		content = generator.render(
			domain=domain,
			upstream=getattr(settings, "CUSTOM_DOMAIN_NGINX_UPSTREAM", "http://127.0.0.1:8000"),
			ssl_cert_path=cert_path,
			ssl_key_path=key_path,
			force_https=bool(getattr(settings, "CUSTOM_DOMAIN_FORCE_HTTPS", False)),
		)
		generator.write_config(domain=domain, content=content)
		generator.test_config()
		generator.reload()

	def _rollback_certificate(self, cert_path: str, key_path: str, backup_cert: str | None, backup_key: str | None):
		if backup_cert and cert_path:
			shutil.copy2(backup_cert, cert_path)
		if backup_key and key_path:
			shutil.copy2(backup_key, key_path)

	def _create_backup(self, source: str):
		if not source:
			return None
		path = Path(source)
		if not path.exists() or not path.is_file():
			return None
		backup_fd, backup_path = tempfile.mkstemp(prefix="wasla-ssl-backup-", suffix=path.suffix or ".pem")
		os.close(backup_fd)
		shutil.copy2(path, backup_path)
		return backup_path

	def _safe_unlink(self, path: str | None):
		if not path:
			return
		try:
			Path(path).unlink(missing_ok=True)
		except Exception:
			return
