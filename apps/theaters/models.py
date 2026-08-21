from django.db import models
from django.utils.text import slugify
from core.models import TimeStampedModel

class City(TimeStampedModel):
    """
    Metropolitan or municipality hosting cinema theaters and showtimes.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name="City Name",
        help_text="Name of the city (e.g. Mumbai, Hyderabad, Bengaluru)."
    )
    state = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="State",
        help_text="State or province location."
    )
    slug = models.SlugField(
        max_length=120,
        unique=True,
        blank=True,
        help_text="URL slug generated from city name."
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'City'
        verbose_name_plural = 'Cities'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}, {self.state}" if self.state else self.name


class Theater(TimeStampedModel):
    """
    Physical cinema venue containing multiple screens/auditoriums.
    """
    name = models.CharField(
        max_length=150,
        db_index=True,
        verbose_name="Theater Name",
        help_text="Commercial name of theater (e.g., PVR Forum Mall, INOX GVK One)."
    )
    slug = models.SlugField(
        max_length=180,
        blank=True,
        help_text="URL slug for theater page."
    )
    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name='theaters',
        help_text="City where theater is located."
    )
    address = models.TextField(
        help_text="Full street address and landmark details."
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS Latitude coordinate for map integration."
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="GPS Longitude coordinate for map integration."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Operational status flag."
    )

    class Meta:
        ordering = ['city', 'name']
        verbose_name = 'Theater'
        verbose_name_plural = 'Theaters'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['city', 'is_active']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.city.name}")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.city.name}"


class Screen(TimeStampedModel):
    """
    Auditorium/Screen room inside a Theater.
    Defines technology format and capacity bounds.
    """
    SCREEN_TYPE_CHOICES = (
        ('2D', 'Standard 2D'),
        ('3D', 'RealD 3D'),
        ('IMAX_3D', 'IMAX 3D'),
        ('4DX', '4DX Motion & Effects'),
        ('DOLBY_ATMOS', 'Dolby Atmos Cinema'),
    )

    theater = models.ForeignKey(
        Theater,
        on_delete=models.CASCADE,
        related_name='screens',
        help_text="Parent theater hosting this screen."
    )
    name = models.CharField(
        max_length=50,
        verbose_name="Screen Name",
        help_text="Auditorium identifier (e.g. Screen 1, Audi 3)."
    )
    screen_type = models.CharField(
        max_length=20,
        choices=SCREEN_TYPE_CHOICES,
        default='2D',
        help_text="Projection and sound format installed on screen."
    )
    total_seats = models.PositiveIntegerField(
        default=100,
        help_text="Total seating capacity of screen."
    )

    class Meta:
        ordering = ['theater', 'name']
        verbose_name = 'Screen'
        verbose_name_plural = 'Screens'
        constraints = [
            models.UniqueConstraint(
                fields=['theater', 'name'],
                name='unique_theater_screen_name'
            )
        ]

    def __str__(self):
        return f"{self.theater.name} - {self.name} ({self.get_screen_type_display()})"


class Seat(TimeStampedModel):
    """
    Individual seat entity mapped within a specific Screen layout grid.
    """
    SEAT_TYPE_CHOICES = (
        ('REGULAR', 'Regular Tier'),
        ('PREMIUM', 'Premium Tier'),
        ('VIP', 'VIP Luxury Tier'),
        ('RECLINER', 'Recliner Bed Tier'),
    )

    screen = models.ForeignKey(
        Screen,
        on_delete=models.CASCADE,
        related_name='seats',
        help_text="Auditorium screen hosting this seat."
    )
    row = models.CharField(
        max_length=5,
        verbose_name="Row Letter",
        help_text="Seating row code (e.g. A, B, C... M)."
    )
    number = models.PositiveIntegerField(
        verbose_name="Seat Number",
        help_text="Seat sequence number along the row (e.g. 1, 2, 12)."
    )
    seat_type = models.CharField(
        max_length=20,
        choices=SEAT_TYPE_CHOICES,
        default='REGULAR',
        help_text="Pricing tier and comfort classification."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Operational state (e.g., set to False if under repair)."
    )

    class Meta:
        ordering = ['row', 'number']
        verbose_name = 'Seat'
        verbose_name_plural = 'Seats'
        constraints = [
            models.UniqueConstraint(
                fields=['screen', 'row', 'number'],
                name='unique_screen_seat'
            )
        ]
        indexes = [
            models.Index(fields=['screen', 'seat_type']),
        ]

    def __str__(self):
        return f"{self.screen.theater.name} [{self.screen.name}] - {self.row}{self.number} ({self.seat_type})"
