from decimal import Decimal
import uuid
from django.db import models
from django.conf import settings
from core.models import TimeStampedModel

class Booking(TimeStampedModel):
    """
    Primary Ticket Booking header record representing a user's reservation for a show.
    Manages payment status, QR code generation state, and seat allocations.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending Payment'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('EXPIRED', 'Expired / Timed Out'),
    )

    booking_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        verbose_name="Booking Reference Code",
        help_text="Unique 12-character booking reference code (e.g. CP-8X92K4)."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        help_text="Authenticated user who initiated the booking."
    )
    show = models.ForeignKey(
        'shows.Show',
        on_delete=models.CASCADE,
        related_name='bookings',
        help_text="Showtime screening reserved."
    )
    total_seats = models.PositiveIntegerField(
        default=1,
        help_text="Total number of seats booked in this transaction."
    )
    total_price = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        help_text="Subtotal sum of seat prices before fees."
    )
    convenience_fee = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal('30.00'),
        help_text="Service and convenience fee in INR."
    )
    grand_total = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        help_text="Final payable amount (total_price + convenience_fee)."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True,
        help_text="Transaction confirmation status."
    )
    qr_code = models.ImageField(
        upload_to='qrcodes/',
        blank=True,
        null=True,
        help_text="Generated QR code image for ticket scanning."
    )
    pdf_ticket = models.FileField(
        upload_to='tickets/',
        blank=True,
        null=True,
        help_text="Generated PDF ticket file for download."
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Booking'

    @property
    def booked_at(self):
        return self.created_at

    @property
    def total_amount(self):
        return self.grand_total

    @property
    def seats_booked(self):
        return self.total_seats
        verbose_name_plural = 'Bookings'
        indexes = [
            models.Index(fields=['booking_number']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['show', 'status']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]


    def save(self, *args, **kwargs):
        if not self.booking_number:
            self.booking_number = f"CP-{uuid.uuid4().hex[:8].upper()}"
        if not self.grand_total and self.total_price:
            self.grand_total = self.total_price + self.convenience_fee
        super().save(*args, **kwargs)

    def cancel_booking(self):
        """Cancels booking and releases seats back to show pool."""
        if self.status in ['CONFIRMED', 'PENDING']:
            self.status = 'CANCELLED'
            self.show.available_seats += self.total_seats
            self.show.save(update_fields=['available_seats'])
            self.save(update_fields=['status'])

    def __str__(self):
        return f"Booking #{self.booking_number} - {self.user.email} - {self.show.movie.title} ({self.total_seats} seats)"


class BookingSeat(TimeStampedModel):
    """
    Junction entity representing an individual seat reserved under a specific Booking.
    Enforces seat locking and avoids double-booking.
    """
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name='booked_seats',
        help_text="Parent booking transaction."
    )
    seat = models.ForeignKey(
        'theaters.Seat',
        on_delete=models.CASCADE,
        related_name='booking_assignments',
        help_text="Individual seat reserved."
    )
    price = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Specific price charged for this seat."
    )

    class Meta:
        ordering = ['seat__row', 'seat__number']
        verbose_name = 'Booked Seat'
        verbose_name_plural = 'Booked Seats'
        constraints = [
            models.UniqueConstraint(
                fields=['booking', 'seat'],
                name='unique_booking_seat_assignment'
            )
        ]

    def __str__(self):
        return f"Booking {self.booking.booking_number} - Seat {self.seat.row}{self.seat.number}"
