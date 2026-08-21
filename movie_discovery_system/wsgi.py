"""
WSGI config for movie_discovery_system project.
"""

import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie_discovery_system.settings.dev')

application = get_wsgi_application()
