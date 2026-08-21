from django.contrib import admin
from .models import DailyAnalyticsSummary

@admin.register(DailyAnalyticsSummary)
class DailyAnalyticsSummaryAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'total_bookings', 'total_tickets_sold', 'gross_revenue', 'average_occupancy_rate')
    search_fields = ('date',)
    ordering = ('-date',)
