"""
WSGI config for movie_discovery_system project.
"""

import os
from django.core.wsgi import get_wsgi_application

if os.getenv('RENDER') or os.getenv('DJANGO_ENV') == 'production' or os.getenv('DEBUG', 'False').lower() not in ('true', '1', 't'):
    default_settings = 'movie_discovery_system.settings.prod'
else:
    default_settings = 'movie_discovery_system.settings.dev'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', default_settings)

application = get_wsgi_application()

