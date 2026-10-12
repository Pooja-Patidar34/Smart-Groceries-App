# project_name/celery.py
import os
from celery import Celery

# Set default Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "CuokkaSmartGroceries.settings")

app = Celery("CuokkaSmartGroceries")

# Use Redis as broker
app.conf.broker_url = "redis://localhost:6379/0"

# Load task modules from all registered Django apps
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
