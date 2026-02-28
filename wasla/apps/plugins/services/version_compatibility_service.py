from __future__ import annotations

from django.conf import settings

from apps.plugins.models import Plugin


class PluginVersionCompatibilityService:
    @staticmethod
    def _parse_version(version: str) -> tuple[int, int, int]:
        value = (version or "0.0.0").strip()
        parts = value.split(".")
        nums: list[int] = []
        for i in range(3):
            try:
                nums.append(int(parts[i]))
            except Exception:
                nums.append(0)
        return tuple(nums)  # type: ignore[return-value]

    @staticmethod
    def get_core_version() -> str:
        return (getattr(settings, "APP_VERSION", "1.0.0") or "1.0.0").strip()

    @staticmethod
    def assert_compatible(plugin: Plugin) -> None:
        registration = getattr(plugin, "registration", None)
        if registration is None:
            raise ValueError("Plugin is not registered")
        if not registration.verified:
            raise ValueError("Plugin registration is not verified")

        core = PluginVersionCompatibilityService._parse_version(PluginVersionCompatibilityService.get_core_version())
        min_v = PluginVersionCompatibilityService._parse_version(registration.min_core_version)

        if core < min_v:
            raise ValueError(
                f"Plugin requires Wassla core >= {registration.min_core_version}"
            )

        if (registration.max_core_version or "").strip():
            max_v = PluginVersionCompatibilityService._parse_version(registration.max_core_version)
            if core > max_v:
                raise ValueError(
                    f"Plugin supports Wassla core <= {registration.max_core_version}"
                )
