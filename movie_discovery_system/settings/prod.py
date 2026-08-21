"""
Production settings for CinePass project.
"""

from .base import *
import os

SECRET_KEY = os.environ.get('SECRET_KEY', SECRET_KEY)
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')

# Parse ALLOWED_HOSTS safely
allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_env.split(',') if host.strip()]

# Automatically add Render hostnames and wildcards
render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

if '.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.onrender.com')

if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['cinepass-r9o8.onrender.com', '.onrender.com', 'localhost', '127.0.0.1', '*']

# CSRF Trusted Origins for Render
csrf_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_env.split(',') if origin.strip()]
if render_hostname:
    CSRF_TRUSTED_ORIGINS.append(f'https://{render_hostname}')
if 'https://*.onrender.com' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(['https://*.onrender.com', 'https://cinepass-r9o8.onrender.com'])

# Security Settings for Production HTTPS deployment
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False') == 'True'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
