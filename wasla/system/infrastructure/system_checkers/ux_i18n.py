from __future__ import annotations

from pathlib import Path

from django.conf import settings

from system.domain.go_live_checks.types import GoLiveCheckItem, LEVEL_P1


class UXI18nReadinessChecker:
    category_key = "ux_i18n"
    category_label = "UX/i18n readiness"

    def run(self) -> list[GoLiveCheckItem]:
        items: list[GoLiveCheckItem] = []

        languages = dict(getattr(settings, "LANGUAGES", []) or [])
        has_ar = "ar" in languages
        has_en = "en" in languages
        languages_ok = has_ar and has_en
        items.append(
            GoLiveCheckItem(
                key="ux_i18n.languages",
                label="Arabic and English configured",
                ok=languages_ok,
                level=LEVEL_P1,
                message=""
                if languages_ok
                else "Ensure LANGUAGES includes both Arabic (ar) and English (en).",
                category=self.category_key,
            )
        )

        default_lang = (getattr(settings, "LANGUAGE_CODE", "") or "").strip()
        default_ok = bool(default_lang) and default_lang in languages
        items.append(
            GoLiveCheckItem(
                key="ux_i18n.default_language",
                label="Default language is supported",
                ok=default_ok,
                level=LEVEL_P1,
                message=""
                if default_ok
                else "Set LANGUAGE_CODE to one of the configured LANGUAGES.",
                category=self.category_key,
            )
        )

        auth_ok, auth_message = _check_auth_templates()
        items.append(
            GoLiveCheckItem(
                key="ux_i18n.auth_templates",
                label="Auth templates do not use dashboard sidebar",
                ok=auth_ok,
                level=LEVEL_P1,
                message=auth_message,
                category=self.category_key,
            )
        )

        return items


def _check_auth_templates() -> tuple[bool, str]:
    base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
    auth_dirs = [
        base_dir / "templates" / "auth",
        base_dir / "templates" / "registration",
    ]
    flagged: list[str] = []
    for root in auth_dirs:
        if not root.exists():
            continue
        for template_path in root.rglob("*.html"):
            try:
                content = template_path.read_text(encoding="utf-8")
            except OSError:
                flagged.append(str(template_path))
                continue
            if "dashboard_base.html" in content or "web/partials/sidebar.html" in content:
                flagged.append(str(template_path))

    if not flagged:
        return True, ""

    short_list = ", ".join(flagged[:5])
    message = f"Auth templates must not extend dashboard layout: {short_list}"
    if len(flagged) > 5:
        message = f"{message} (+{len(flagged) - 5} more)"
    return False, message
