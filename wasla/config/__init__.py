try:
    import pymysql
except ModuleNotFoundError:
    pymysql = None
else:
    pymysql.install_as_MySQLdb()

# Import Celery app for worker discovery
from .celery import app as celery_app

__all__ = ("celery_app",)
