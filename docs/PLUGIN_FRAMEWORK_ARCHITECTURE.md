# Wassla Scalable Plugin Architecture

## Overview
This framework provides a secure, tenant-aware plugin platform with:
- Plugin registration contract
- Permission scopes per plugin (deny-by-default)
- Event dispatcher (webhook/event-bus style)
- Per-tenant plugin enable/disable
- Version compatibility guardrails

Implementation modules:
- Models: `apps/plugins/models.py`
- Lifecycle service: `apps/plugins/services/lifecycle_service.py`
- Version checker: `apps/plugins/services/version_compatibility_service.py`
- Scope guard: `apps/plugins/services/security_scope_service.py`
- Event bus: `apps/plugins/services/event_dispatcher.py`

---

## 1) Plugin Registration Model
`PluginRegistration` (one-to-one with `Plugin`) defines runtime contract:
- `plugin_key` (unique identifier)
- `entrypoint`
- `min_core_version` / `max_core_version`
- `isolation_mode` (`process`/`sandbox`)
- `verified` (required before enable)

This prevents unregistered/unverified plugins from activation.

---

## 2) Permission Scope per Plugin
`PluginPermissionScope` stores explicit allowed scopes, e.g.:
- `plugin.lifecycle.enable`
- `plugin.lifecycle.disable`
- `plugin.lifecycle.uninstall`
- `events.consume.order.created`

`PluginSecurityScopeService.require_scope()` enforces no implicit permissions.

---

## 3) Event Bus / Webhook Dispatch Layer
`PluginEventDispatcher.dispatch_event(tenant_id, event_key, payload)`:
1. Selects active subscriptions in same tenant only.
2. Confirms plugin is active and compatible.
3. Confirms plugin has `events.consume.<event_key>` scope.
4. Writes delivery record (`PluginEventDelivery`) with status:
   - `queued`, `skipped`, `failed`, `delivered`.

This provides traceability and retry-ready persistence.

---

## 4) Per-Tenant Enable/Disable
`InstalledPlugin` + `PluginLifecycleService` already handle store/tenant state.
Enhancements now enforce:
- Registration + compatibility required on enable.
- Scoped lifecycle permissions required for enable/disable/uninstall.
- Dependency checks preserved.

---

## 5) Version Compatibility Checker
`PluginVersionCompatibilityService.assert_compatible(plugin)` compares:
- Wassla core version (`APP_VERSION`)
- Plugin min/max supported core versions

Out-of-range plugins are blocked before activation.

---

## Isolation and Security Boundaries
- Tenant isolation: event subscriptions/deliveries filtered by `tenant_id`.
- Permission isolation: explicit plugin scopes only.
- Runtime gate: unverified plugin registration is blocked.
- No security bypass: lifecycle operations call scope + compatibility checks.

---

## Typical Flow
1. Create `Plugin`.
2. Create `PluginRegistration` (verified=true after validation).
3. Add `PluginPermissionScope` entries.
4. Install/enable plugin for tenant store.
5. Register `PluginEventSubscription` entries.
6. Dispatch domain events through `PluginEventDispatcher`.

---

## Testing Coverage
Added/updated tests in `apps/plugins/tests.py` for:
- Missing required plan feature block
- Dependency uninstall protection
- Activation/deactivation audit logs
- Unverified registration block
- Event dispatcher tenant isolation + scope enforcement

---

## Management API Endpoints

## Superuser (platform-level)
- `GET/POST /api/plugins/registry/`
- `PATCH /api/plugins/registry/{registration_id}/`
- `GET/POST /api/plugins/{plugin_id}/scopes/`
- `DELETE /api/plugins/scopes/{scope_id}/`

These endpoints enforce superuser access and are intended for platform admin operations.

## Tenant/store-level (merchant RBAC)
- `GET/POST /api/stores/{store_id}/plugins/event-subscriptions/`
- `PATCH /api/stores/{store_id}/plugins/event-subscriptions/{subscription_id}/`

Isolation guarantees:
- Store + tenant ownership checks via guards (`require_store`, `require_tenant`)
- Subscription mutations only allowed for active installed plugins in same tenant/store
