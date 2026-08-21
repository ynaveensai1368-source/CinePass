from django.db import models
from core.models import TimeStampedModel

class DailyAnalyticsSummary(TimeStampedModel):
    """
    Pre-calculated daily metric snapshot for admin and theater manager dashboards.
    Aggregates booking counts, occupancy rates, and gross revenue per theater.
    """
    date = models.DateField(
        unique=True,
        db_index=True,
        help_text="Target metric aggregation date."
    )
    total_bookings = models.PositiveIntegerField(
        default=0,
        help_text="Count of confirmed bookings on this day."
    )
    total_tickets_sold = models.PositiveIntegerField(
        default=0,
        help_text="Sum of seat tickets sold."
    )
    gross_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total ticket revenue in INR."
    )
    average_occupancy_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Percentage average seat occupancy across all screens."
    )

    class Meta:
        ordering = ['-date']
        verbose_name = 'Daily Analytics Summary'
        verbose_name_plural = 'Daily Analytics Summaries'

    def __str__(self):
        return f"Analytics Summary for {self.date} - ₹{self.gross_revenue}"
