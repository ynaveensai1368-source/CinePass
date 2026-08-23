from django.db import models
from core.models import TimeStampedModel

class Show(TimeStampedModel):
    """
    Scheduled movie screening at a specific theater screen and showtime slot.
    Serves as the anchor entity for ticket seat selection and bookings.
    """
    STATUS_CHOICES = (
        ('UPCOMING', 'Upcoming / Scheduled'),
        ('OPEN', 'Booking Open'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    )

    movie = models.ForeignKey(
        'movies.Movie',
        on_delete=models.CASCADE,
        related_name='shows',
        help_text="Movie scheduled for screening."
    )
    language = models.ForeignKey(
        'movies.Language',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shows',
        help_text="Screening audio/dub language for this show."
    )
    screen = models.ForeignKey(
        'theaters.Screen',
        on_delete=models.CASCADE,
        related_name='shows',
        help_text="Auditorium screen hosting the show."
    )
    start_time = models.DateTimeField(
        db_index=True,
        verbose_name="Screening Start Time",
        help_text="Exact timestamp when the show begins."
    )
    end_time = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Screening End Time",
        help_text="Estimated timestamp when show ends (including trailers)."
    )
    base_price = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        db_index=True,
        verbose_name="Base Ticket Price",
        help_text="Standard regular seat ticket price in INR."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='OPEN',
        db_index=True,
        help_text="Booking status lifecycle stage."
    )
    available_seats = models.PositiveIntegerField(
        default=100,
        help_text="Current real-time tally of unbooked seats."
    )

    class Meta:
        ordering = ['start_time']
        verbose_name = 'Show'
        verbose_name_plural = 'Shows'
        constraints = [
            models.UniqueConstraint(
                fields=['screen', 'start_time'],
                name='unique_screen_show_start_time'
            )
        ]
        indexes = [
            models.Index(fields=['start_time']),
            models.Index(fields=['movie', 'start_time']),
            models.Index(fields=['screen', 'start_time']),
            models.Index(fields=['base_price']),
            models.Index(fields=['status']),
        ]

    def save(self, *args, **kwargs):
        if not self.available_seats and self.screen:
            self.available_seats = self.screen.total_seats
        super().save(*args, **kwargs)

    def __str__(self):
        date_str = self.start_time.strftime('%b %d, %Y %I:%M %p')
        return f"{self.movie.title} @ {self.screen.theater.name} ({self.screen.name}) - {date_str}"

    @property
    def is_available(self):
        return self.available_seats > 0 and self.status == 'OPEN'

    @property
    def theater(self):
        return self.screen.theater if self.screen else None

    @property
    def show_time(self):
        return self.start_time

    @property
    def ticket_price(self):
        return self.base_price

    @property
    def show_language(self):
        if self.language_id:
            return self.language
        return self.movie.language if self.movie else None

    @property
    def language_name(self):
        lang = self.show_language
        return lang.name if lang else 'Original'


class SeatReservation(TimeStampedModel):
    """
    Temporary seat reservation holding selected seats for 2 minutes during checkout.
    Enforces atomic locking to prevent double-booking.
    """
    STATUS_CHOICES = (
        ('ACTIVE', 'Active 2-Min Hold'),
        ('RESERVED', 'Temporarily Reserved'),
        ('EXPIRED', 'Reservation Expired'),
        ('CONVERTED', 'Converted to Booking'),
        ('CONFIRMED', 'Confirmed into Booking'),
        ('CANCELLED', 'Cancelled'),
    )

    show = models.ForeignKey(
        Show,
        on_delete=models.CASCADE,
        related_name='seat_reservations',
        help_text="Showtime for which the seat is reserved."
    )
    seat = models.ForeignKey(
        'theaters.Seat',
        on_delete=models.CASCADE,
        related_name='reservations',
        help_text="Specific seat reserved."
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='seat_reservations',
        null=True,
        blank=True,
        help_text="Authenticated user holding the reservation."
    )
    reservation_token = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        default='',
        help_text="Unique UUID grouping token for multi-seat 2-minute hold."
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        db_index=True,
        help_text="Anonymous visitor session key."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        db_index=True
    )
    total_amount = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=0,
        help_text="Calculated total price for reserved seats."
    )
    reserved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Exact timestamp (2 minutes from creation) when reservation expires."
    )

    class Meta:
        ordering = ['-reserved_at']
        verbose_name = 'Seat Reservation'
        verbose_name_plural = 'Seat Reservations'
        indexes = [
            models.Index(fields=['show', 'seat', 'status']),
            models.Index(fields=['expires_at', 'status']),
            models.Index(fields=['reservation_token']),
            models.Index(fields=['user', 'status']),
        ]

    def is_active(self):
        from django.utils import timezone
        return self.status in ['ACTIVE', 'RESERVED'] and self.expires_at > timezone.now()

    def __str__(self):
        user_info = self.user.email if self.user else f"Session: {self.session_key}"
        return f"Reservation [{self.reservation_token[:8]}] for {self.seat.row}{self.seat.number} on Show #{self.show.id} ({self.status})"


class ShowSeat(TimeStampedModel):
    """
    Per-show seat availability status and pricing assignment.
    Connects physical Seat to a specific Show instance.
    """
    STATUS_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('RESERVED', 'Temporarily Reserved'),
        ('BOOKED', 'Booked'),
    )

    show = models.ForeignKey(
        Show,
        on_delete=models.CASCADE,
        related_name='show_seats',
        help_text="Scheduled showtime."
    )
    seat = models.ForeignKey(
        'theaters.Seat',
        on_delete=models.CASCADE,
        related_name='show_assignments',
        help_text="Physical seat location."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AVAILABLE',
        db_index=True
    )
    price = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Calculated price for this specific seat on this show."
    )
    reservation = models.ForeignKey(
        SeatReservation,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='show_seats',
        help_text="Active 2-minute reservation holding this seat."
    )
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='show_seats',
        help_text="Confirmed booking for this seat."
    )

    class Meta:
        ordering = ['seat__row', 'seat__number']
        verbose_name = 'Show Seat'
        verbose_name_plural = 'Show Seats'
        constraints = [
            models.UniqueConstraint(
                fields=['show', 'seat'],
                name='unique_show_seat'
            )
        ]
        indexes = [
            models.Index(fields=['show', 'status']),
            models.Index(fields=['show', 'seat']),
        ]

    def __str__(self):
        return f"Show #{self.show.id} - Seat {self.seat.row}{self.seat.number} ({self.status}) - ₹{self.price}"

