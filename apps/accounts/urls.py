from django.urls import path
from .views import (
    RegisterView,
    CustomLoginView,
    CustomLogoutView,
    ProfileView,
    BookingHistoryView,
    PaymentHistoryView,
)

app_name = 'accounts'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('bookings/', BookingHistoryView.as_view(), name='booking_history'),
    path('payments/', PaymentHistoryView.as_view(), name='payment_history'),
]
