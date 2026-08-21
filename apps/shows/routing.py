from django.urls import re_path
from .consumers import SeatAvailabilityConsumer

websocket_urlpatterns = [
    re_path(r'^ws/shows/(?P<show_id>\d+)/seats/$', SeatAvailabilityConsumer.as_asgi()),
]
