"""
Development settings for CinePass project.
"""

from .base import *
import os

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-cinepass-2026')
allowed_hosts_raw = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost,testserver,.onrender.com')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_raw.split(',') if h.strip()]
render_host = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if render_host and render_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_host)
if '.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.onrender.com')

# Dynamic email backend: uses SMTP if configured in .env, otherwise console backend for local testing
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend' if os.getenv('EMAIL_HOST_PASSWORD') and os.getenv('EMAIL_HOST_PASSWORD') != 'abcdefghijklmnop' else 'django.core.mail.backends.console.EmailBackend'
)

# Execute Celery tasks eagerly during development & unit testing
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
