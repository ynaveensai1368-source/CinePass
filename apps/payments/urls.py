from django.urls import path
from .views import (
    CheckoutView,
    VerifyPaymentAPIView,
    PaymentWebhookAPIView,
    PaymentFailureAPIView,
    PaymentRetryAPIView,
    DemoSignPaymentAPIView,
)

app_name = 'payments'

urlpatterns = [
    path('checkout/<int:show_id>/', CheckoutView.as_view(), name='checkout'),
    path('verify/', VerifyPaymentAPIView.as_view(), name='verify'),
    path('webhook/', PaymentWebhookAPIView.as_view(), name='webhook'),
    path('api/failed/', PaymentFailureAPIView.as_view(), name='api_failed'),
    path('api/cancel/', PaymentFailureAPIView.as_view(), name='api_cancel'),
    path('api/retry/', PaymentRetryAPIView.as_view(), name='api_retry'),
    path('api/demo-sign/', DemoSignPaymentAPIView.as_view(), name='api_demo_sign'),
]
