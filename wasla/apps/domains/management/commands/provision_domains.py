from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django.conf import settings

from apps.domains.application.provision_domain import ProvisionDomainCommand, ProvisionDomainUseCase
from apps.domains.application.verify_domain import VerifyDomainCommand, VerifyDomainUseCase
from apps.domains.infrastructure.nginx_generator import NginxConfigGenerator
from apps.tenants.models import StoreDomain


class Command(BaseCommand):
    help = "Provision custom domains safely (verify, SSL, nginx config, reload)."

    def handle(self, *args, **options):
        generator = NginxConfigGenerator()
        domains = list(
            StoreDomain.objects.filter(
                status__in=[
                    StoreDomain.STATUS_PENDING_VERIFICATION,
                    StoreDomain.STATUS_PENDING,
                    StoreDomain.STATUS_VERIFIED,
                    StoreDomain.STATUS_SSL_PENDING,
                ]
            ).order_by("created_at")
        )
        if not domains:
            self.stdout.write(self.style.SUCCESS("No pending domains."))
            return

        for domain in domains:
            self.stdout.write(f"Processing {domain.domain} ({domain.status})")
            if domain.status in (StoreDomain.STATUS_PENDING_VERIFICATION, StoreDomain.STATUS_PENDING):
                config_path = NginxConfigGenerator.config_path(domain.domain)
                previous = config_path.read_text(encoding="utf-8") if config_path.exists() else None
                if getattr(settings, "CUSTOM_DOMAIN_NGINX_ENABLED", False):
                    try:
                        content = generator.render(
                            domain=domain.domain,
                            upstream=getattr(settings, "CUSTOM_DOMAIN_NGINX_UPSTREAM", "http://127.0.0.1:8000"),
                            ssl_cert_path="",
                            ssl_key_path="",
                            force_https=False,
                        )
                        generator.write_config(domain=domain.domain, content=content)
                        generator.test_config()
                        generator.reload()
                    except Exception as exc:
                        if previous is None:
                            config_path.unlink(missing_ok=True)
                        else:
                            config_path.write_text(previous, encoding="utf-8")
                        domain.status = StoreDomain.STATUS_FAILED
                        domain.save(update_fields=["status"])
                        self.stderr.write(f"Nginx setup failed for {domain.domain}: {exc}")
                        continue
                try:
                    VerifyDomainUseCase.execute(VerifyDomainCommand(domain_id=domain.id))
                except Exception as exc:
                    self.stderr.write(f"Verification failed for {domain.domain}: {exc}")
                    continue

            domain.refresh_from_db()
            if domain.status not in (StoreDomain.STATUS_VERIFIED, StoreDomain.STATUS_SSL_PENDING):
                continue

            config_path = NginxConfigGenerator.config_path(domain.domain)
            previous = config_path.read_text(encoding="utf-8") if config_path.exists() else None

            try:
                ProvisionDomainUseCase.execute(ProvisionDomainCommand(domain_id=domain.id))
                if getattr(settings, "CUSTOM_DOMAIN_NGINX_ENABLED", False):
                    generator.test_config()
                    generator.reload()
            except Exception as exc:
                if previous is None:
                    config_path.unlink(missing_ok=True)
                else:
                    config_path.write_text(previous, encoding="utf-8")
                domain.status = StoreDomain.STATUS_FAILED
                domain.save(update_fields=["status"])
                self.stderr.write(f"Provision failed for {domain.domain}: {exc}")
                continue

            with transaction.atomic():
                domain = StoreDomain.objects.select_for_update().filter(id=domain.id).first()
                if domain:
                    domain.status = StoreDomain.STATUS_SSL_ACTIVE
                    domain.last_check_at = timezone.now()
                    domain.save(update_fields=["status", "last_check_at"])

            self.stdout.write(self.style.SUCCESS(f"Provisioned {domain.domain}"))
