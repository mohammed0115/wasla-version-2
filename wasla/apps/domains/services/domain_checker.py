"""
Domain health checking service for DNS, HTTP, and SSL verification.
"""

from __future__ import annotations

import logging
import socket
from datetime import datetime
from typing import Optional

import requests
from django.utils import timezone

logger = logging.getLogger("domain_monitoring")


class DomainChecker:
    """Check domain health metrics."""

    HTTP_TIMEOUT = 3
    DNS_TIMEOUT = 5

    def __init__(self, domain: str):
        """Initialize checker for a domain."""
        self.domain = domain
        self.errors = []

    def check_dns(self) -> bool:
        """
        Check if domain DNS resolves.

        Returns:
            bool: True if DNS resolves to valid IP
        """
        try:
            result = socket.gethostbyname(self.domain)
            if not result:
                self.errors.append("DNS resolution returned no IP")
                return False
            return True
        except socket.gaierror as e:
            self.errors.append(f"DNS resolution failed: {str(e)}")
            return False
        except Exception as e:
            self.errors.append(f"Unexpected DNS check error: {str(e)}")
            return False

    def check_http(self) -> bool:
        """
        Check if domain is HTTP/HTTPS reachable.

        Returns:
            bool: True if HTTP endpoint is reachable
        """
        try:
            # Try both HTTPS and HTTP
            for protocol in ["https", "http"]:
                try:
                    url = f"{protocol}://{self.domain}/"
                    response = requests.get(
                        url,
                        timeout=self.HTTP_TIMEOUT,
                        verify=False,
                        allow_redirects=True,
                    )
                    # Accept any response status (even error pages mean server is reachable)
                    return True
                except requests.exceptions.ConnectionError:
                    continue
                except requests.exceptions.Timeout:
                    continue
                except requests.exceptions.RequestException:
                    continue

            self.errors.append("HTTP endpoint unreachable on both HTTP and HTTPS")
            return False

        except Exception as e:
            self.errors.append(f"Unexpected HTTP check error: {str(e)}")
            return False

    def check_ssl(self) -> dict:
        """
        Check SSL certificate status and expiry.

        Returns:
            dict: With keys:
                - valid (bool): Certificate is valid and not expired
                - expires_at (datetime): Certificate expiry date
                - error (str): Error message if invalid
        """
        try:
            import ssl
            from datetime import datetime as dt

            # Create SSL context
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED

            # Get certificate
            with socket.create_connection((self.domain, 443), timeout=self.DNS_TIMEOUT) as sock:
                with context.wrap_socket(sock, server_hostname=self.domain) as ssock:
                    cert = ssock.getpeercert()

                    if not cert:
                        return {
                            "valid": False,
                            "expires_at": None,
                            "error": "No SSL certificate found",
                        }

                    # Parse expiry date
                    not_after = cert.get("notAfter")
                    if not_after:
                        expires_at = self.parse_ssl_not_after(not_after)
                        # Make timezone-aware
                        expires_at = timezone.make_aware(expires_at)

                        # Check if expired
                        if expires_at <= timezone.now():
                            return {
                                "valid": False,
                                "expires_at": expires_at,
                                "error": "SSL certificate has expired",
                            }

                        return {
                            "valid": True,
                            "expires_at": expires_at,
                            "error": "",
                        }

                    return {
                        "valid": False,
                        "expires_at": None,
                        "error": "Could not determine SSL expiry date",
                    }

        except ssl.SSLError as e:
            return {
                "valid": False,
                "expires_at": None,
                "error": f"SSL error: {str(e)}",
            }
        except socket.timeout:
            return {
                "valid": False,
                "expires_at": None,
                "error": "SSL check timeout",
            }
        except Exception as e:
            return {
                "valid": False,
                "expires_at": None,
                "error": f"SSL check error: {str(e)}",
            }

    @staticmethod
    def parse_ssl_not_after(not_after: str) -> datetime:
        return datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
