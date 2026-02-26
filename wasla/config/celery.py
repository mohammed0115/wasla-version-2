from __future__ import annotations

import os

try:
	from celery import Celery
	from celery.schedules import crontab
except Exception:  # pragma: no cover
	Celery = None

	def crontab(*_args, **_kwargs):
		return None

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


if Celery is None:
	class _NoopCeleryApp:
		conf = type("_NoopConf", (), {"beat_schedule": {}})()

		def config_from_object(self, *_args, **_kwargs):
			return None

		def autodiscover_tasks(self, *_args, **_kwargs):
			return None

	app = _NoopCeleryApp()
else:
	app = Celery("wasla")
	app.config_from_object("django.conf:settings", namespace="CELERY")
	app.autodiscover_tasks()

	app.conf.beat_schedule = {
		"domains-health-check-daily": {
			"task": "apps.domains.tasks.check_domain_health",
			"schedule": crontab(minute=0, hour=2),
		},
		"domains-ssl-renewal-daily": {
			"task": "apps.domains.tasks.renew_expiring_ssl",
			"schedule": crontab(minute=30, hour=2),
		},
	}
