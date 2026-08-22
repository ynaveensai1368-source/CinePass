from django.urls import path
from .views import (
    BookTicketsView,
    CancelBookingView,
    DownloadTicketPDFView,
    ResendTicketEmailView,
    VerifyTicketView,
    VerifyPaymentAPIView,
)

app_name = 'bookings'

urlpatterns = [
    path('show/<int:show_id>/book/', BookTicketsView.as_view(), name='book_tickets'),
    path('cancel/<int:booking_id>/', CancelBookingView.as_view(), name='cancel_booking'),
    path('ticket/<int:booking_id>/pdf/', DownloadTicketPDFView.as_view(), name='download_ticket'),
    path('ticket/<int:booking_id>/email/', ResendTicketEmailView.as_view(), name='resend_ticket_email'),
    path('tickets/verify/<str:token>/', VerifyTicketView.as_view(), name='verify_ticket'),
    path('api/tickets/verify/<str:token>/', VerifyTicketView.as_view(), name='api_verify_ticket'),
    path('api/payments/verify/', VerifyPaymentAPIView.as_view(), name='api_verify_payment'),
]

