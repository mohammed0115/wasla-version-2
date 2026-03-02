from __future__ import annotations

from django.conf import settings


class ReadWriteRouter:
    """Route reads to replica (when enabled) and writes to primary."""

    def __init__(self) -> None:
        self.primary_alias = getattr(settings, "DB_PRIMARY_ALIAS", "default")
        self.read_alias = getattr(settings, "DB_READ_REPLICA_ALIAS", "replica")
        self.read_enabled = bool(getattr(settings, "DB_READ_REPLICA_ENABLED", False)) and (
            self.read_alias in settings.DATABASES
        )
        self.excluded_apps = set(getattr(settings, "DB_READ_ROUTER_EXCLUDED_APPS", []) or [])

    def db_for_read(self, model, **hints):
        if not self.read_enabled:
            return None
        instance = hints.get("instance")
        if instance is not None and getattr(instance._state, "db", None):
            return instance._state.db
        if hints.get("force_primary"):
            return self.primary_alias
        if model._meta.app_label in self.excluded_apps:
            return self.primary_alias
        return self.read_alias

    def db_for_write(self, model, **hints):
        return self.primary_alias

    def allow_relation(self, obj1, obj2, **hints):
        dbs = {self.primary_alias, self.read_alias}
        if obj1._state.db in dbs and obj2._state.db in dbs:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == self.read_alias:
            return False
        return None
