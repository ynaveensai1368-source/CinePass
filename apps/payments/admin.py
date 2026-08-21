from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'payment_id', 'order_id', 'amount', 'provider', 'status', 'created_at')
    list_filter = ('provider', 'status', 'created_at')
    search_fields = ('payment_id', 'order_id', 'booking__booking_number', 'booking__user__email')
    ordering = ('-created_at',)
