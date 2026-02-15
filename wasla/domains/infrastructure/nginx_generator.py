from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from django.conf import settings

from security.settings_helpers import sanitize_filename
from tenants.domain.policies import normalize_domain

try:  # optional dependency
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except Exception:  # pragma: no cover
    Environment = None


class NginxConfigGenerator:
    def __init__(self):
        template_dir = Path(getattr(settings, "NGINX_TEMPLATE_DIR", "infrastructure/nginx"))
        if not Environment:
            raise RuntimeError("Jinja2 is required for Nginx template rendering.")
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(enabled_extensions=()),
        )
        self.template_name = getattr(settings, "NGINX_DOMAIN_TEMPLATE", "domain.conf.j2")

    def render(
        self,
        *,
        domain: str,
        upstream: str,
        ssl_cert_path: str = "",
        ssl_key_path: str = "",
        force_https: bool = False,
    ) -> str:
        template = self.env.get_template(self.template_name)
        return template.render(
            domain=domain,
            upstream=upstream,
            ssl_cert_path=ssl_cert_path,
            ssl_key_path=ssl_key_path,
            force_https=force_https,
        )

    @staticmethod
    def config_path(domain: str) -> Path:
        normalized = normalize_domain(domain)
        if not normalized:
            raise ValueError("Invalid domain for nginx config.")
        safe_name = sanitize_filename(normalized)
        domains_dir = Path(
            getattr(settings, "CUSTOM_DOMAIN_NGINX_DOMAINS_DIR", "/etc/nginx/conf.d/wasla_domains")
        )
        domains_dir.mkdir(parents=True, exist_ok=True)
        return domains_dir / f"{safe_name}.conf"

    @staticmethod
    def write_config(*, domain: str, content: str) -> Path:
        path = NginxConfigGenerator.config_path(domain)
        tmp = path.with_suffix(".conf.tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)
        return path

    @staticmethod
    def test_config() -> None:
        test_cmd = getattr(settings, "CUSTOM_DOMAIN_NGINX_TEST_CMD", "nginx -t")
        subprocess.run(shlex.split(test_cmd), check=True, capture_output=True, text=True)

    @staticmethod
    def reload() -> None:
        reload_cmd = getattr(settings, "CUSTOM_DOMAIN_NGINX_RELOAD_CMD", "systemctl reload nginx")
        subprocess.run(shlex.split(reload_cmd), check=True, capture_output=True, text=True)
