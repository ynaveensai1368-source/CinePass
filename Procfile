web: python manage.py migrate --noinput && python manage.py seed_data && daphne -b 0.0.0.0 -p $PORT movie_discovery_system.asgi:application
worker: celery -A movie_discovery_system worker --loglevel=info

