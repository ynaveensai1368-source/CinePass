"""
Settings initialization module.
Dynamically routes to production (prod.py) or development (dev.py) based on environment.
"""
import os

env_mode = os.getenv('DJANGO_ENV', '').lower()
is_render = bool(os.getenv('RENDER') or os.getenv('RENDER_EXTERNAL_HOSTNAME') or os.getenv('DATABASE_URL'))
is_prod = env_mode in ('production', 'prod') or is_render or (os.getenv('DEBUG', 'False').lower() not in ('true', '1', 't'))

if is_prod and not os.getenv('FORCE_DEV_SETTINGS'):
    from .prod import *
else:
    from .dev import *
