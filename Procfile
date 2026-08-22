web: python manage.py migrate --noinput && python manage.py sync_movies --pages 2 && daphne -b 0.0.0.0 -p $PORT movie_discovery_system.asgi:application
worker: celery -A movie_discovery_system worker --loglevel=info
