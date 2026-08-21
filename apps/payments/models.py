from django.db import models
from core.models import TimeStampedModel

class Payment(TimeStampedModel):
    """
    Financial payment ledger tracking gateway orders, transaction verification,
    and refund statuses for ticket bookings.
    """
    PROVIDER_CHOICES = (
        ('RAZORPAY', 'Razorpay Gateway'),
        ('STRIPE', 'Stripe Payments'),
        ('MOCK', 'Mock / Developer Gateway'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending Payment'),
        ('SUCCESS', 'Payment Successful'),
        ('FAILED', 'Payment Failed'),
        ('REFUNDED', 'Payment Refunded'),
    )

    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='payment',
        help_text="Target booking associated with this payment transaction."
    )
    payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Gateway Transaction ID",
        help_text="Unique transaction reference identifier returned by payment gateway (e.g. pay_L89Xz2)."
    )
    order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Gateway Order ID",
        help_text="Merchant order reference created before payment modal."
    )
    signature = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="HMAC SHA256 signature payload for verification."
    )
    amount = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        help_text="Total transaction amount paid in INR."
    )
    currency = models.CharField(
        max_length=10,
        default='INR',
        help_text="Currency code (e.g. INR)."
    )
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='RAZORPAY',
        help_text="Payment processing provider."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Current state of payment processing."
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        indexes = [
            models.Index(fields=['payment_id']),
            models.Index(fields=['order_id']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        booking_ref = getattr(self.booking, 'booking_number', getattr(self, 'booking_id', 'N/A'))
        return f"Payment #{self.pk} for Booking {booking_ref} - Status: {self.status}"

