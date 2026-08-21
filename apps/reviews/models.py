from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel

class Review(TimeStampedModel):
    """
    User Ratings & Text Reviews for catalog movies.
    Includes spoiler flags, helpfulness vote counts, and numerical ratings (1-10).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="User submitting the rating or review."
    )
    movie = models.ForeignKey(
        'movies.Movie',
        on_delete=models.CASCADE,
        related_name='reviews',
        help_text="Movie being reviewed."
    )
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Rating score on scale of 1 to 10."
    )
    headline = models.CharField(
        max_length=150,
        blank=True,
        help_text="Short summary headline for review."
    )
    comment = models.TextField(
        help_text="Detailed user review text."
    )
    is_spoiler = models.BooleanField(
        default=False,
        help_text="Flag indicating if text contains plot spoilers."
    )
    likes_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of helpful votes from other users."
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'movie'],
                name='unique_user_movie_review'
            )
        ]
        indexes = [
            models.Index(fields=['movie', '-rating']),
            models.Index(fields=['movie', '-created_at']),
        ]

    def __str__(self):
        user_obj = getattr(self, 'user', None)
        user_email = getattr(user_obj, 'email', None) or f"User #{getattr(self, 'user_id', 'N/A')}"

        movie_obj = getattr(self, 'movie', None)
        movie_title = getattr(movie_obj, 'title', None) or f"Movie #{getattr(self, 'movie_id', 'N/A')}"

        rating = getattr(self, 'rating', '?')
        return f"Review by {user_email} for {movie_title} ({rating}/10)"


class ReviewReport(TimeStampedModel):
    """
    User reports flagging inappropriate or offensive review content.
    Prevents duplicate reports from the same user for the same review.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending Moderation'),
        ('RESOLVED', 'Content Removed / Action Taken'),
        ('DISMISSED', 'Report Dismissed'),
    )

    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='reports',
        help_text="Target review being flagged."
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_reports',
        help_text="Reporting user account."
    )
    reason = models.TextField(
        help_text="Reason why content is inappropriate or offensive."
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Review Report'
        verbose_name_plural = 'Review Reports'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'review'],
                name='unique_user_review_report'
            )
        ]
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]

    def __str__(self):
        user_email = getattr(self.user, 'email', None) or f"User #{self.user_id}"
        return f"Report #{self.id} on Review #{self.review_id} by {user_email} ({self.status})"

