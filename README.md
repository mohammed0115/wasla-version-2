# wasla-version-2

## Platform Default Store
- Set `WASSLA_BASE_DOMAIN` for the root domain.
- Run `python manage.py ensure_platform_store` to create the platform tenant, store, and root-domain mappings.

## Onboarding Email
- `WASSLA_SUPPORT_EMAIL` controls the support contact used in onboarding emails.
- `WASSLA_EMAIL_ASYNC_ENABLED` toggles async sending (default: `True`).
