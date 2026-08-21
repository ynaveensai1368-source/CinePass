import os
import asyncio
import logging

# Configure default settings module (production on Render or if configured, dev otherwise)
if os.getenv('RENDER') or os.getenv('DJANGO_ENV') == 'production' or os.getenv('DEBUG', 'False').lower() not in ('true', '1', 't'):
    default_settings = 'movie_discovery_system.settings.prod'
else:
    default_settings = 'movie_discovery_system.settings.dev'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', default_settings)

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import shows.routing

logger = logging.getLogger('cinepass.asgi')


class GracefulCancellationMiddleware:
    """
    ASGI middleware that cleanly catches and silences client cancellations / disconnects
    (asyncio.CancelledError) without raising unhandled exceptions in production.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        try:
            await self.app(scope, receive, send)
        except asyncio.CancelledError:
            # Client disconnected or request was cancelled by reverse proxy
            logger.debug(f"ASGI request cancelled for scope type: {scope.get('type')}")
        except Exception as exc:
            logger.error(f"Unhandled exception in ASGI pipeline: {exc}", exc_info=True)
            raise


application = ProtocolTypeRouter({
    "http": GracefulCancellationMiddleware(django_asgi_app),
    "websocket": GracefulCancellationMiddleware(
        AuthMiddlewareStack(
            URLRouter(
                shows.routing.websocket_urlpatterns
            )
        )
    ),
})

