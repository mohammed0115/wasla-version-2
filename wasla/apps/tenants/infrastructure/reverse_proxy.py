from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from django.conf import settings

from apps.tenants.domain.errors import CustomDomainVerificationError
from apps.tenants.domain.policies import normalize_domain


class NginxReverseProxyAdapter:
    @staticmethod
    def ensure_domain_config(
        domain: str,
        *,
        upstream: str,
        ssl_cert_path: str = "",
        ssl_key_path: str = "",
    ) -> None:
        if not getattr(settings, "CUSTOM_DOMAIN_NGINX_ENABLED", False):
            return

        normalized = normalize_domain(domain)
        if not normalized:
            raise CustomDomainVerificationError("Invalid domain for Nginx configuration.")

        domains_dir = Path(getattr(settings, "CUSTOM_DOMAIN_NGINX_DOMAINS_DIR", "/etc/nginx/wassla/domains"))
        domains_dir.mkdir(parents=True, exist_ok=True)

        config_path = domains_dir / f"{normalized}.conf"
        previous = config_path.read_text(encoding="utf-8") if config_path.exists() else None

        config_text = NginxReverseProxyAdapter._render_config(
            domain=normalized,
            upstream=upstream,
            ssl_cert_path=ssl_cert_path,
            ssl_key_path=ssl_key_path,
            force_https=bool(getattr(settings, "CUSTOM_DOMAIN_FORCE_HTTPS", False)),
        )
        config_path.write_text(config_text, encoding="utf-8")

        try:
            NginxReverseProxyAdapter._test_and_reload()
        except Exception:
            if previous is None:
                config_path.unlink(missing_ok=True)
            else:
                config_path.write_text(previous, encoding="utf-8")
            raise

    @staticmethod
    def remove_domain_config(domain: str) -> None:
        if not getattr(settings, "CUSTOM_DOMAIN_NGINX_ENABLED", False):
            return

        normalized = normalize_domain(domain)
        if not normalized:
            return

        domains_dir = Path(getattr(settings, "CUSTOM_DOMAIN_NGINX_DOMAINS_DIR", "/etc/nginx/wassla/domains"))
        config_path = domains_dir / f"{normalized}.conf"
        if config_path.exists():
            config_path.unlink()
        NginxReverseProxyAdapter._test_and_reload()

    @staticmethod
    def _render_config(
        *,
        domain: str,
        upstream: str,
        ssl_cert_path: str,
        ssl_key_path: str,
        force_https: bool,
    ) -> str:
        upstream_target = upstream
        if not upstream_target.startswith("http"):
            upstream_target = f"http://{upstream_target}"

        http_block = f"""
server {{
    listen 80;
    server_name {domain};
    {'return 301 https://$host$request_uri;' if force_https and ssl_cert_path and ssl_key_path else ''}
    location /.well-known/wassla-domain-verification/ {{
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass {upstream_target};
    }}
    location / {{
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass {upstream_target};
    }}
}}
"""

        ssl_block = ""
        if ssl_cert_path and ssl_key_path:
            ssl_block = f"""
server {{
    listen 443 ssl;
    server_name {domain};
    ssl_certificate {ssl_cert_path};
    ssl_certificate_key {ssl_key_path};
    location / {{
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_pass {upstream_target};
    }}
}}
"""
        return (http_block + ssl_block).strip() + "\n"

    @staticmethod
    def _test_and_reload() -> None:
        if not getattr(settings, "CUSTOM_DOMAIN_NGINX_RELOAD_IN_REQUEST", False):
            return
        test_cmd = getattr(settings, "CUSTOM_DOMAIN_NGINX_TEST_CMD", "nginx -t")
        reload_cmd = getattr(settings, "CUSTOM_DOMAIN_NGINX_RELOAD_CMD", "nginx -s reload")

        try:
            subprocess.run(shlex.split(test_cmd), check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            raise CustomDomainVerificationError(
                f"Nginx config test failed: {exc.stderr or exc.stdout or str(exc)}"
            ) from exc

        try:
            subprocess.run(shlex.split(reload_cmd), check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            raise CustomDomainVerificationError(
                f"Nginx reload failed: {exc.stderr or exc.stdout or str(exc)}"
            ) from exc
