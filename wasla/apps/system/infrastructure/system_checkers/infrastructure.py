from __future__ import annotations

from django.conf import settings

from apps.system.domain.go_live_checks.types import GoLiveCheckItem, LEVEL_P0, LEVEL_P1


class InfrastructureReadinessChecker:
    category_key = "infrastructure"
    category_label = "Infrastructure readiness"

    def run(self) -> list[GoLiveCheckItem]:
        items: list[GoLiveCheckItem] = []

        engine = (settings.DATABASES.get("default", {}).get("ENGINE") or "").strip()
        engine_ok = engine in {
            "django.db.backends.sqlite3",
            "django.db.backends.mysql",
            "django.db.backends.postgresql",
        }
        items.append(
            GoLiveCheckItem(
                key="infra.db_engine",
                label="Database engine is supported",
                ok=engine_ok,
                level=LEVEL_P0,
                message=""
                if engine_ok
                else f"Unsupported database engine configured: {engine or 'unknown'}",
                category=self.category_key,
            )
        )

        hosts = [h.strip() for h in (getattr(settings, "ALLOWED_HOSTS", []) or []) if h.strip()]
        host_ok = True
        if not getattr(settings, "DEBUG", False):
            host_ok = any(
                h not in {"localhost", "127.0.0.1", "[::1]"} and not h.startswith("127.")
                for h in hosts
            ) or "*" in hosts
        items.append(
            GoLiveCheckItem(
                key="infra.allowed_hosts",
                label="ALLOWED_HOSTS configured for production",
                ok=host_ok,
                level=LEVEL_P0,
                message="" if host_ok else "Set ALLOWED_HOSTS to real production domains.",
                category=self.category_key,
            )
        )

        static_root = str(getattr(settings, "STATIC_ROOT", "") or "").strip()
        static_ok = bool(static_root)
        items.append(
            GoLiveCheckItem(
                key="infra.static_root",
                label="Static root configured",
                ok=static_ok,
                level=LEVEL_P1,
                message="" if static_ok else "Set DJANGO_STATIC_ROOT for collected static files.",
                category=self.category_key,
            )
        )

        environment = (getattr(settings, "ENVIRONMENT", "") or "").strip().lower()
        ssl_ok = True
        if environment == "production":
            ssl_ok = bool(getattr(settings, "SECURE_SSL_REDIRECT", False)) and bool(
                getattr(settings, "SESSION_COOKIE_SECURE", False)
            )
        items.append(
            GoLiveCheckItem(
                key="infra.ssl_redirect",
                label="HTTPS redirects and secure cookies in production",
                ok=ssl_ok,
                level=LEVEL_P1,
                message=""
                if ssl_ok
                else "Enable SECURE_SSL_REDIRECT and SESSION_COOKIE_SECURE for production.",
                category=self.category_key,
            )
        )

        return items
