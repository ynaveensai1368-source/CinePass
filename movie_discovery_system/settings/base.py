"""
Base settings for CinePass project.
Shared settings across development, staging, and production environments.
"""

from pathlib import Path
import os
import sys
import dj_database_url

# Python 3.14 compatibility patch for Django Context copy
try:
    from django.template.context import Context
    def _context_copy(self):
        duplicate = Context()
        duplicate.dicts = self.dicts[:]
        return duplicate
    Context.__copy__ = _context_copy  # type: ignore

except Exception:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except Exception:
    pass

# Add apps directory to Python path for clean modular imports
sys.path.insert(0, os.path.join(BASE_DIR, 'apps'))

# Secret Key (Overridden in environment / dev.py / prod.py)
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-cinepass-foundation-key-change-in-production')

# Custom User Authentication Model
AUTH_USER_MODEL = 'accounts.User'

# Core Application Definitions
INSTALLED_APPS = [
    # ASGI Server
    'daphne',

    # Django Built-in Apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-Party Apps
    'channels',
    'crispy_forms',
    'crispy_bootstrap5',

    # Custom Local Apps
    'core',
    'accounts',
    'movies',
    'theaters',
    'shows',
    'bookings',
    'payments',
    'reviews',
    'dashboard',
    'recommendations',
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'movie_discovery_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'movie_discovery_system.wsgi.application'
ASGI_APPLICATION = 'movie_discovery_system.asgi.application'

# Database Configuration using dj_database_url
# Default fallback to PostgreSQL local database uri, or SQLite if configured for local dev testing
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv(
            'DATABASE_URL',
            f"sqlite:///{os.path.join(BASE_DIR, 'db.sqlite3')}"
        ),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

if DATABASES['default'].get('ENGINE') == 'django.db.backends.sqlite3':
    DATABASES['default'].setdefault('OPTIONS', {})['timeout'] = 30


# Password Validation Rules
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization & Localization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static Files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
WHITENOISE_MANIFEST_STRICT = False
WHITENOISE_USE_FINDERS = True


# Media Files (Posters, User Avatars, QR Codes, PDF Tickets)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default Primary Key Auto Field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# TMDb API Configuration
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '476a98b00b55454480f9e727bfbd4030')
TMDB_ACCESS_TOKEN = os.getenv('TMDB_ACCESS_TOKEN', '')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE_URL = 'https://image.tmdb.org/t/p/w500'

# Razorpay Integration Settings (Test Mode)
RAZORPAY_KEY_ID = os.getenv('RAZORPAY_KEY_ID', 'rzp_test_cinepass_key')
RAZORPAY_KEY_SECRET = os.getenv('RAZORPAY_KEY_SECRET', 'cinepass_secret_key')
RAZORPAY_WEBHOOK_SECRET = os.getenv('RAZORPAY_WEBHOOK_SECRET', 'cinepass_webhook_secret')

# Celery & Redis Settings
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'max_retries': 0,
    'interval_start': 0,
    'interval_step': 0,
    'interval_max': 0,
}

# ASGI Application & Django Channels WebSocket Layer
ASGI_APPLICATION = 'movie_discovery_system.asgi.application'

REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer' if os.getenv('USE_IN_MEMORY_CHANNEL_LAYER', 'True').lower() == 'true' else 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [REDIS_URL],
        } if os.getenv('USE_IN_MEMORY_CHANNEL_LAYER', 'True').lower() != 'true' else {},
    },
}

# Custom Authentication Backends (Support Login via Email OR Username)
AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Email Configuration (Resilient IPv4 Gmail SMTP)
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'apps.bookings.resilient_smtp.ResilientEmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', 'ynaveensai1368@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', 'qqlnguwcodkiuhju')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'CinePass <ynaveensai1368@gmail.com>')
EMAIL_TIMEOUT = 10

# Google OAuth 2.0 Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '684928194012-cinepass-demo.apps.googleusercontent.com')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')


# CORS & CSRF Trusted Origins
_cors_env = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:8000,https://cinepass-r9o8.onrender.com')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_env.split(',') if origin.strip()]
if 'https://cinepass-r9o8.onrender.com' not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append('https://cinepass-r9o8.onrender.com')

_csrf_env = os.getenv('CSRF_TRUSTED_ORIGINS', 'http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000,http://127.0.0.1:3000,https://cinepass-r9o8.onrender.com,https://*.onrender.com')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_env.split(',') if origin.strip()]
for default_origin in [
    'https://cinepass-r9o8.onrender.com',
    'https://*.onrender.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]:
    if default_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(default_origin)

_render_host = os.getenv('RENDER_EXTERNAL_HOSTNAME')
if _render_host:
    _render_origin = f'https://{_render_host}'
    if _render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_render_origin)

# Professional Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
        'cinepass': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

