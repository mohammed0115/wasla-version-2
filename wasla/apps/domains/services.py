"""
Domain Services - Core business logic for custom domain + SSL management.

Services:
- DomainVerificationService: DNS ownership verification
- CertificateService: SSL certificate issuance/renewal via Let's Encrypt
- DomainHealthCheckService: Domain health monitoring
- DomainManagementService: Orchestrates all domain operations
"""

import logging
import dns.resolver
import requests
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any

from django.utils import timezone
from django.conf import settings

from apps.tenants.models import StoreDomain, DomainAuditLog

logger = logging.getLogger(__name__)


class DomainVerificationService:
    """Handles DNS-based domain ownership verification."""

    @staticmethod
    def verify_dns_txt(domain: str, token: str) -> bool:
        """
        Verify ownership via DNS TXT record.
        Expects: _wasla-verify.<domain> TXT <token>
        """
        try:
            verification_domain = f"_wasla-verify.{domain}"
            
            # Query TXT records
            answers = dns.resolver.resolve(verification_domain, "TXT")
            
            for rdata in answers:
                # TXT records are returned as quoted strings
                txt_value = str(rdata).strip('"')
                if txt_value == token:
                    logger.info(f"DNS TXT verification successful for {domain}")
                    return True
            
            logger.warning(f"DNS TXT token mismatch for {domain}")
            return False
            
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, Exception) as e:
            logger.error(f"DNS TXT verification failed for {domain}: {str(e)}")
            return False

    @staticmethod
    def verify_dns_cname(domain: str, platform_domain: str) -> bool:
        """
        Verify ownership via CNAME record pointing to platform.
        Expects: www.<domain> CNAME <platform_domain>
        """
        try:
            www_domain = f"www.{domain}"
            
            answers = dns.resolver.resolve(www_domain, "CNAME")
            
            for rdata in answers:
                cname_target = str(rdata).rstrip(".")
                if cname_target == platform_domain or cname_target == f"{platform_domain}.":
                    logger.info(f"DNS CNAME verification successful for {domain}")
                    return True
            
            logger.warning(f"DNS CNAME target mismatch for {domain}")
            return False
            
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, Exception) as e:
            logger.error(f"DNS CNAME verification failed for {domain}: {str(e)}")
            return False

    @staticmethod
    def verify_dns_resolves(domain: str, expected_ip: Optional[str] = None) -> bool:
        """
        Verify domain resolves to expected IP.
        If expected_ip is None, just check that it resolves.
        """
        try:
            answers = dns.resolver.resolve(domain, "A")
            
            resolved_ips = [str(rdata) for rdata in answers]
            
            if expected_ip:
                if expected_ip in resolved_ips:
                    logger.info(f"DNS A record verification successful for {domain}")
                    return True
                logger.warning(f"DNS A record IP mismatch for {domain}: got {resolved_ips}, expected {expected_ip}")
                return False
            else:
                logger.info(f"Domain {domain} resolves to {resolved_ips}")
                return True
                
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, Exception) as e:
            logger.error(f"DNS A record verification failed for {domain}: {str(e)}")
            return False


class CertificateService:
    """
    Manages SSL certificate issuance and renewal via Let's Encrypt.
    
    Integrates with:
    - certbot (or acme library) for cert issuance
    - Traefik/Caddy configuration for automated renewal
    """
    
    ACME_ENDPOINT = "https://acme-v02.api.letsencrypt.org/directory"
    ACME_STAGING_ENDPOINT = "https://acme-staging-v02.api.letsencrypt.org/directory"
    
    def __init__(self):
        self.is_staging = getattr(settings, "LETS_ENCRYPT_STAGING", False)
        self.endpoint = self.ACME_STAGING_ENDPOINT if self.is_staging else self.ACME_ENDPOINT
        self.acme_email = getattr(settings, "LETS_ENCRYPT_EMAIL", "admin@wasla.local")

    def request_certificate(self, domain: StoreDomain) -> Dict[str, Any]:
        """
        Request SSL certificate for domain.
        
        Returns:
            {
                "success": bool,
                "cert_path": str,
                "key_path": str,
                "expires_at": datetime,
                "error": str (if failed)
            }
        """
        try:
            # In production, this would call certbot or ACME client library
            # For MVP, we use a generic ACME-compatible approach
            
            logger.info(f"Requesting certificate for {domain.domain}")
            
            # Check if domain resolves (must be resolvable for HTTP-01 challenge)
            if not DomainVerificationService.verify_dns_resolves(domain.domain):
                return {
                    "success": False,
                    "error": "Domain does not resolve. Ensure DNS A record points to this server's IP."
                }
            
            # Call certbot (via subprocess or Docker)
            result = self._issue_certificate_via_certbot(domain)
            
            if result["success"]:
                logger.info(f"Certificate issued for {domain.domain}")
                # Typically expires in 90 days
                expires_at = timezone.now() + timedelta(days=90)
                return {
                    "success": True,
                    "cert_path": result.get("cert_path"),
                    "key_path": result.get("key_path"),
                    "expires_at": expires_at,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Certificate issuance failed")
                }
                
        except Exception as e:
            logger.error(f"Certificate request failed for {domain.domain}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def renew_certificate(self, domain: StoreDomain) -> Dict[str, Any]:
        """Renew SSL certificate before expiration."""
        logger.info(f"Renewing certificate for {domain.domain}")
        
        try:
            # Check if renewal needed (< 30 days to expiry)
            if domain.cert_expires_at:
                days_until_expiry = (domain.cert_expires_at - timezone.now()).days
                if days_until_expiry > 30:
                    return {
                        "success": True,
                        "reason": f"Certificate not yet expiring (expires in {days_until_expiry} days)"
                    }
            
            # Call certbot renew
            result = self._renew_certificate_via_certbot(domain)
            
            if result["success"]:
                expires_at = timezone.now() + timedelta(days=90)
                return {
                    "success": True,
                    "expires_at": expires_at,
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Certificate renewal failed")
                }
                
        except Exception as e:
            logger.error(f"Certificate renewal failed for {domain.domain}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _issue_certificate_via_certbot(self, domain: StoreDomain) -> Dict[str, Any]:
        """
        Helper: Issue certificate via certbot (subprocess call).
        
        In production, this would:
        1. Call: certbot certonly --webroot -w /var/www/certbot -d <domain> --email <email> --agree-tos --no-eff-email
        2. Store cert paths
        3. Return success/error
        
        For MVP, we simulate success and store paths.
        """
        try:
            import subprocess
            
            if self.is_staging:
                staging_flag = ["--staging"]
            else:
                staging_flag = []
            
            cmd = [
                "certbot",
                "certonly",
                "--webroot",
                "-w", "/var/www/certbot",
                "--non-interactive",
                "--agree-tos",
                "--no-eff-email",
                "-d", domain.domain,
                "--email", self.acme_email,
                *staging_flag
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Certificate paths (standard Let's Encrypt location)
                cert_path = f"/etc/letsencrypt/live/{domain.domain}/fullchain.pem"
                key_path = f"/etc/letsencrypt/live/{domain.domain}/privkey.pem"
                
                return {
                    "success": True,
                    "cert_path": cert_path,
                    "key_path": key_path,
                }
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"Certbot call failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _renew_certificate_via_certbot(self, domain: StoreDomain) -> Dict[str, Any]:
        """Helper: Renew certificate via certbot."""
        try:
            import subprocess
            
            cmd = [
                "certbot",
                "renew",
                "--cert-name", domain.domain,
                "--force-renewal",
                "--non-interactive",
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                return {"success": True}
            else:
                error_msg = result.stderr or result.stdout or "Unknown error"
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            logger.error(f"Certbot renew failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


class DomainHealthCheckService:
    """Monitors domain health: DNS, HTTPS, certificate validity."""

    @staticmethod
    def check_domain_health(domain: StoreDomain) -> Dict[str, Any]:
        """
        Comprehensive health check:
        1. DNS resolves to platform IP
        2. HTTPS returns 200/302
        3. Certificate is valid
        """
        health = {
            "domain": domain.domain,
            "dns_ok": False,
            "https_ok": False,
            "cert_ok": False,
            "overall_ok": False,
            "errors": []
        }
        
        try:
            # 1. Check DNS
            platform_ip = getattr(settings, "PLATFORM_IP", None)
            if DomainVerificationService.verify_dns_resolves(domain.domain, platform_ip):
                health["dns_ok"] = True
            else:
                health["errors"].append("Domain does not resolve to platform IP")
            
            # 2. Check HTTPS
            try:
                response = requests.head(
                    f"https://{domain.domain}/",
                    timeout=10,
                    allow_redirects=True,
                    verify=True  # Verify SSL certificate
                )
                if response.status_code in [200, 301, 302]:
                    health["https_ok"] = True
                else:
                    health["errors"].append(f"HTTPS returned {response.status_code}")
            except requests.exceptions.SSLError as e:
                health["errors"].append(f"SSL certificate error: {str(e)}")
            except requests.exceptions.RequestException as e:
                health["errors"].append(f"HTTPS request failed: {str(e)}")
            
            # 3. Check certificate expiration
            if domain.cert_expires_at:
                days_until_expiry = (domain.cert_expires_at - timezone.now()).days
                if days_until_expiry > 0:
                    health["cert_ok"] = True
                    health["days_until_expiry"] = days_until_expiry
                    if days_until_expiry < 30:
                        health["errors"].append(f"Certificate expires in {days_until_expiry} days")
                else:
                    health["errors"].append("Certificate has expired")
            else:
                health["errors"].append("No certificate issued")
            
            health["overall_ok"] = health["dns_ok"] and health["https_ok"] and health["cert_ok"]
            
        except Exception as e:
            logger.error(f"Health check failed for {domain.domain}: {str(e)}")
            health["errors"].append(str(e))
        
        return health


class DomainManagementService:
    """
    Orchestrates domain lifecycle:
    1. Add domain (PENDING_VERIFICATION)
    2. Verify ownership (-> VERIFIED)
    3. Request certificate (-> CERT_REQUESTED -> CERT_ISSUED)
    4. Activate (-> ACTIVE)
    5. Monitor (health checks)
    6. Renew (on expiration)
    """

    @staticmethod
    def add_domain(tenant, domain_name: str, verification_method: str = "dns_txt", created_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Add a new custom domain to the store.
        
        Returns:
            {
                "success": bool,
                "domain": StoreDomain instance,
                "error": str (if failed)
            }
        """
        domain_name = StoreDomain.normalize_domain(domain_name)
        
        try:
            # Check if domain already exists
            if StoreDomain.objects.filter(domain=domain_name).exists():
                return {
                    "success": False,
                    "error": "This domain is already registered on the platform."
                }
            
            # Generate verification token
            verification_token = StoreDomain.generate_verification_token()
            
            # Create domain record
            domain = StoreDomain.objects.create(
                tenant=tenant,
                domain=domain_name,
                verification_method=verification_method,
                verification_token=verification_token,
                status=StoreDomain.STATUS_PENDING_VERIFICATION,
                next_retry_at=timezone.now()
            )
            
            # Log action
            DomainAuditLog.objects.create(
                domain=domain,
                action=DomainAuditLog.ACTION_CREATED,
                details={
                    "verification_method": verification_method
                },
                performed_by=created_by or "system"
            )
            
            logger.info(f"Domain added: {domain_name} for tenant {tenant.id}")
            
            return {
                "success": True,
                "domain": domain,
                "verification_token": verification_token,
                "instruction": f"Add DNS {verification_method.upper()} record: _wasla-verify.{domain_name} = {verification_token}"
            }
            
        except Exception as e:
            logger.error(f"Failed to add domain {domain_name}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def verify_domain(domain: StoreDomain) -> Dict[str, Any]:
        """
        Verify domain ownership via DNS.
        
        Returns:
            {"success": bool, "error": str (if failed)}
        """
        try:
            verified = False
            
            if domain.verification_method == StoreDomain.METHOD_DNS_TXT:
                verified = DomainVerificationService.verify_dns_txt(domain.domain, domain.verification_token)
            elif domain.verification_method == StoreDomain.METHOD_DNS_CNAME:
                platform_domain = getattr(settings, "PLATFORM_DOMAIN", "wasla.io")
                verified = DomainVerificationService.verify_dns_cname(domain.domain, platform_domain)
            
            if verified:
                domain.status = StoreDomain.STATUS_VERIFIED
                domain.verified_at = timezone.now()
                domain.failure_reason = ""
                domain.retry_count = 0
                domain.next_retry_at = timezone.now()  # Ready for next step immediately
                domain.save(update_fields=[
                    "status", "verified_at", "failure_reason", "retry_count", "next_retry_at"
                ])
                
                DomainAuditLog.objects.create(
                    domain=domain,
                    action=DomainAuditLog.ACTION_VERIFIED,
                    new_status=StoreDomain.STATUS_VERIFIED,
                )
                
                logger.info(f"Domain verified: {domain.domain}")
                
                return {"success": True}
            else:
                domain.increment_retry()
                domain.failure_reason = f"DNS verification failed. Check your DNS records."
                domain.save(update_fields=["retry_count", "next_retry_at", "failure_reason"])
                
                return {
                    "success": False,
                    "error": domain.failure_reason
                }
                
        except Exception as e:
            logger.error(f"Domain verification error: {str(e)}")
            domain.increment_retry()
            domain.failure_reason = str(e)
            domain.save(update_fields=["retry_count", "next_retry_at", "failure_reason"])
            
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def request_certificate(domain: StoreDomain) -> Dict[str, Any]:
        """
        Request SSL certificate from Let's Encrypt.
        """
        try:
            cert_service = CertificateService()
            result = cert_service.request_certificate(domain)
            
            if result["success"]:
                domain.status = StoreDomain.STATUS_CERT_ISSUED
                domain.cert_issued_at = timezone.now()
                domain.cert_expires_at = result.get("expires_at")
                domain.ssl_cert_path = result.get("cert_path", "")
                domain.ssl_key_path = result.get("key_path", "")
                domain.failure_reason = ""
                domain.retry_count = 0
                domain.next_retry_at = timezone.now()
                domain.save(update_fields=[
                    "status", "cert_issued_at", "cert_expires_at",
                    "ssl_cert_path", "ssl_key_path", "failure_reason", "retry_count", "next_retry_at"
                ])
                
                DomainAuditLog.objects.create(
                    domain=domain,
                    action=DomainAuditLog.ACTION_CERT_ISSUED,
                    new_status=StoreDomain.STATUS_CERT_ISSUED,
                )
                
                logger.info(f"Certificate issued for {domain.domain}")
                
                return {"success": True}
            else:
                domain.status = StoreDomain.STATUS_CERT_REQUESTED
                domain.increment_retry()
                domain.failure_reason = result.get("error", "Certificate request failed")
                domain.save(update_fields=["status", "retry_count", "next_retry_at", "failure_reason"])
                
                return {
                    "success": False,
                    "error": domain.failure_reason
                }
                
        except Exception as e:
            logger.error(f"Certificate request error: {str(e)}")
            domain.increment_retry()
            domain.failure_reason = str(e)
            domain.status = StoreDomain.STATUS_FAILED
            domain.save(update_fields=["status", "retry_count", "next_retry_at", "failure_reason"])
            
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def activate_domain(domain: StoreDomain) -> Dict[str, Any]:
        """
        Activate domain: health check + move to ACTIVE.
        """
        try:
            health_check = DomainHealthCheckService.check_domain_health(domain)
            
            if health_check["overall_ok"]:
                domain.status = StoreDomain.STATUS_ACTIVE
                domain.last_checked_at = timezone.now()
                domain.failure_reason = ""
                domain.save(update_fields=["status", "last_checked_at", "failure_reason"])
                
                DomainAuditLog.objects.create(
                    domain=domain,
                    action=DomainAuditLog.ACTION_ACTIVATED,
                    new_status=StoreDomain.STATUS_ACTIVE,
                )
                
                logger.info(f"Domain activated: {domain.domain}")
                
                return {"success": True}
            else:
                domain.status = StoreDomain.STATUS_DEGRADED
                domain.failure_reason = "; ".join(health_check["errors"])
                domain.last_checked_at = timezone.now()
                domain.save(update_fields=["status", "failure_reason", "last_checked_at"])
                
                return {
                    "success": False,
                    "error": domain.failure_reason
                }
                
        except Exception as e:
            logger.error(f"Activation error: {str(e)}")
            domain.status = StoreDomain.STATUS_FAILED
            domain.failure_reason = str(e)
            domain.save(update_fields=["status", "failure_reason"])
            
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def recheck_domain(domain: StoreDomain, requested_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Manual recheck: immediately run verification/activation checks.
        """
        try:
            domain.next_retry_at = timezone.now()
            domain.save(update_fields=["next_retry_at"])
            
            DomainAuditLog.objects.create(
                domain=domain,
                action=DomainAuditLog.ACTION_RECHECKED,
                performed_by=requested_by or "system"
            )
            
            logger.info(f"Domain rechecked (requested by {requested_by}): {domain.domain}")
            
            return {"success": True, "message": "Domain check scheduled immediately"}
            
        except Exception as e:
            logger.error(f"Recheck error: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
