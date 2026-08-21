"""
Global URL Configuration for CinePass Project.
Routes top-level path prefixes to modular application URL routers.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.http import JsonResponse, HttpResponse
from core.views import health_check

def favicon_view(request):
    """Responds to browser favicon requests."""
    return HttpResponse(status=204)

def chrome_devtools_json(request):
    """Responds to Chrome/Chromium DevTools workspace probe."""
    return JsonResponse({}, status=200)

urlpatterns = [
    path('favicon.ico', favicon_view, name='favicon'),
    path('.well-known/appspecific/com.chrome.devtools.json', chrome_devtools_json),
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health_check'),

    path('', include('movies.urls', namespace='movies')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('theaters/', include('theaters.urls', namespace='theaters')),
    path('shows/', include('shows.urls', namespace='shows')),
    path('bookings/', include('bookings.urls', namespace='bookings')),
    path('payments/', include('payments.urls', namespace='payments')),
    path('api/payments/webhook/', include(('payments.urls', 'api_payments'), namespace='api_payments')),
    path('reviews/', include('reviews.urls', namespace='reviews')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('recommendations/', include('recommendations.urls', namespace='recommendations')),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
