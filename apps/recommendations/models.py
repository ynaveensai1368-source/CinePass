from django.db import models
from django.conf import settings
from core.models import TimeStampedModel

class UserInteraction(TimeStampedModel):
    """
    Logs user interactions (page views, search clicks, bookings, favorites)
    used as raw training signal data for content-based & collaborative filtering algorithms.
    """
    INTERACTION_CHOICES = (
        ('VIEW', 'Page Detail View'),
        ('SEARCH', 'Search Result Click'),
        ('BOOKING', 'Completed Booking'),
        ('FAVORITE', 'Added to Watchlist / Favorites'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='interactions',
        null=True,
        blank=True,
        help_text="Authenticated user record."
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        db_index=True,
        help_text="Anonymous visitor session identifier."
    )
    movie = models.ForeignKey(
        'movies.Movie',
        on_delete=models.CASCADE,
        related_name='user_interactions',
        help_text="Target movie item."
    )
    interaction_type = models.CharField(
        max_length=20,
        choices=INTERACTION_CHOICES,
        default='VIEW',
        db_index=True,
        help_text="Type of interaction signal."
    )
    score_weight = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=1.00,
        help_text="Weighted signal strength for recommendation ranking."
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Interaction'
        verbose_name_plural = 'User Interactions'
        indexes = [
            models.Index(fields=['user', 'interaction_type']),
            models.Index(fields=['movie', 'interaction_type']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        user_str = self.user.email if self.user else f"Session: {self.session_key}"
        return f"{user_str} - {self.interaction_type} on {self.movie.title}"
