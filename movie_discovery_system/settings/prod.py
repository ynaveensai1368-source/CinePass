"""
Production settings for CinePass project.
Configured for resilient zero-downtime deployment on Render.
"""

from .base import *
import os
import dj_database_url

SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# ----------------------------------------------------
# Host & Domain Security
# ----------------------------------------------------
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]

render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

for default_host in ['.onrender.com', 'cinepass-r9o8.onrender.com', 'localhost', '127.0.0.1']:
    if default_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(default_host)

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['*']

# ----------------------------------------------------
# CSRF & CORS Security Origins
# ----------------------------------------------------
csrf_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_env.split(',') if origin.strip()]
if render_hostname:
    CSRF_TRUSTED_ORIGINS.append(f'https://{render_hostname}')
for default_csrf in ['https://*.onrender.com', 'https://cinepass-r9o8.onrender.com', 'http://localhost:8000', 'http://127.0.0.1:8000']:
    if default_csrf not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(default_csrf)

cors_env = os.environ.get('CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in cors_env.split(',') if origin.strip()]
if render_hostname:
    CORS_ALLOWED_ORIGINS.append(f'https://{render_hostname}')
for default_cors in ['https://*.onrender.com', 'https://cinepass-r9o8.onrender.com', 'http://localhost:3000', 'http://127.0.0.1:3000']:
    if default_cors not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(default_cors)

# ----------------------------------------------------
# SSL & Cookie Security
# ----------------------------------------------------
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1', 't')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ----------------------------------------------------
# Database Configuration
# ----------------------------------------------------
db_url = os.getenv('DATABASE_URL')
if db_url:
    DATABASES = {
        'default': dj_database_url.config(
            default=db_url,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }

# ----------------------------------------------------
# Redis, Celery & Django Channels WebSocket Layer
# ----------------------------------------------------
redis_url = os.getenv('REDIS_URL') or os.getenv('CELERY_BROKER_URL')
if redis_url:
    CELERY_BROKER_URL = redis_url
    CELERY_RESULT_BACKEND = redis_url

    if os.getenv('USE_IN_MEMORY_CHANNEL_LAYER', 'False').lower() != 'true':
        CHANNEL_LAYERS = {
            'default': {
                'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {
                    'hosts': [redis_url],
                },
            },
        }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# ----------------------------------------------------
# Static Files & WhiteNoise
# ----------------------------------------------------
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_USE_FINDERS = True

# ----------------------------------------------------
# Email Delivery Configuration (Gmail SMTP)
# ----------------------------------------------------
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'ynaveensai1368@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'qqlnguwcodkiuhju')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'CinePass <ynaveensai1368@gmail.com>')
EMAIL_TIMEOUT = 15


