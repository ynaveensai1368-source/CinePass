import os
from celery import Celery

# Set default Django settings module for 'celery' program.
if os.getenv('RENDER') or os.getenv('DJANGO_ENV') == 'production' or os.getenv('DEBUG', 'False').lower() not in ('true', '1', 't'):
    default_settings = 'movie_discovery_system.settings.prod'
else:
    default_settings = 'movie_discovery_system.settings.dev'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', default_settings)

app = Celery('movie_discovery_system')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related config keys should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

