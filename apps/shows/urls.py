from django.urls import path
from .views import ShowSeatSelectionView
from .api_views import (
    ShowSeatLayoutAPIView,
    ReserveSeatsAPIView,
    ReservationDetailAPIView,
)

app_name = 'shows'

urlpatterns = [
    # UI Seat Selection Map
    path('<int:show_id>/seats/', ShowSeatSelectionView.as_view(), name='seat_selection'),
    path('<int:show_id>/select-seats/', ShowSeatSelectionView.as_view(), name='select_seats'),

    # REST API Endpoints
    path('api/<int:show_id>/seats/', ShowSeatLayoutAPIView.as_view(), name='api_show_seats'),
    path('api/<int:show_id>/seats/reserve/', ReserveSeatsAPIView.as_view(), name='api_reserve_seats'),
    path('api/reservations/<str:reservation_token>/', ReservationDetailAPIView.as_view(), name='api_reservation_detail'),
]
