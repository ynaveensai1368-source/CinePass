import csv
from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render, redirect
from django.views import View
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.mixins import UserPassesTestMixin
from django.utils import timezone
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncDate, TruncHour

from bookings.models import Booking
from payments.models import Payment
from movies.models import Movie
from theaters.models import Theater
from accounts.models import User


class StaffAdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser or self.request.user.role in ['SITE_ADMIN', 'THEATER_ADMIN'])


class AdminDashboardView(StaffAdminRequiredMixin, View):
    """
    Comprehensive Admin Analytics Dashboard view with date range filters,
    database aggregations, revenue trends, occupancy, and top performers.
    """
    def get(self, request):
        now = timezone.now()
        period = request.GET.get('period', '30days')

        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == '7days':
            start_date = now - timedelta(days=7)
        elif period == 'this_month':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'this_year':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'custom':
            custom_start = request.GET.get('start_date')
            if custom_start:
                try:
                    start_date = timezone.datetime.strptime(custom_start, '%Y-%m-%d')
                except ValueError:
                    start_date = now - timedelta(days=30)
            else:
                start_date = now - timedelta(days=30)
        else:  # 30days default
            start_date = now - timedelta(days=30)

        # Base booking queryset within date filter
        bookings_qs = Booking.objects.filter(created_at__gte=start_date)

        # 1. Headline KPI Aggregations
        confirmed_qs = bookings_qs.filter(status='CONFIRMED')
        total_revenue = confirmed_qs.aggregate(total=Sum('grand_total'))['total'] or Decimal('0.00')
        total_bookings_count = bookings_qs.count()
        confirmed_bookings_count = confirmed_qs.count()
        total_tickets_sold = confirmed_qs.aggregate(seats=Sum('total_seats'))['seats'] or 0

        cancelled_count = bookings_qs.filter(status='CANCELLED').count()
        cancellation_rate = (cancelled_count / total_bookings_count * 100) if total_bookings_count > 0 else 0.0

        # Payments status tally & refund statistics
        payments_qs = Payment.objects.filter(created_at__gte=start_date)
        successful_payments = payments_qs.filter(status='SUCCESS').count()
        failed_payments = payments_qs.filter(status='FAILED').count()
        refunded_payments_qs = payments_qs.filter(status='REFUNDED')
        refunded_payments_count = refunded_payments_qs.count()
        total_refund_amount = refunded_payments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # 2. Daily Revenue & Booking Trend Chart Data (TruncDate)
        daily_trends = confirmed_qs.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            revenue=Sum('grand_total'),
            bookings=Count('id')
        ).order_by('date')

        trend_labels = [t['date'].strftime('%b %d') for t in daily_trends if t['date']]
        trend_revenue = [float(t['revenue']) for t in daily_trends if t['date']]
        trend_bookings = [t['bookings'] for t in daily_trends if t['date']]

        # 3. Top Performing Movies by Revenue
        top_movies = confirmed_qs.values(
            'show__movie__title'
        ).annotate(
            revenue=Sum('grand_total'),
            tickets=Sum('total_seats')
        ).order_by('-revenue')[:5]

        # 4. Theater Occupancy & Revenue Breakdown (Calculates exact occupancy percentage)
        theater_performance_raw = confirmed_qs.values(
            'show__screen__theater__name',
            'show__screen__theater__city__name'
        ).annotate(
            revenue=Sum('grand_total'),
            tickets=Sum('total_seats'),
            capacity=Sum('show__screen__total_seats')
        ).order_by('-revenue')[:5]

        theater_performance = []
        for tp in theater_performance_raw:
            tickets = tp['tickets'] or 0
            capacity = tp['capacity'] or 1
            occupancy = round((tickets / capacity * 100), 1) if capacity > 0 else 0.0
            theater_performance.append({
                'theater_name': tp['show__screen__theater__name'],
                'city_name': tp['show__screen__theater__city__name'],
                'revenue': float(tp['revenue']),
                'tickets': tickets,
                'capacity': capacity,
                'occupancy_percentage': occupancy
            })

        # 5. Peak Booking Hours (TruncHour)
        peak_hours_raw = confirmed_qs.annotate(
            hour=TruncHour('created_at')
        ).values('hour').annotate(
            count=Count('id')
        ).order_by('-count')[:6]

        peak_hours = []
        for ph in peak_hours_raw:
            if ph['hour']:
                peak_hours.append({
                    'hour_str': ph['hour'].strftime('%I:00 %p'),
                    'count': ph['count']
                })

        # 6. User Growth Analytics
        total_users = User.objects.count()
        recent_users_count = User.objects.filter(date_joined__gte=start_date).count()

        context = {
            'period': period,
            'total_revenue': float(total_revenue),
            'total_bookings_count': total_bookings_count,
            'confirmed_bookings_count': confirmed_bookings_count,
            'total_tickets_sold': total_tickets_sold,
            'cancellation_rate': round(cancellation_rate, 1),
            'successful_payments': successful_payments,
            'failed_payments': failed_payments,
            'refunded_payments_count': refunded_payments_count,
            'total_refund_amount': float(total_refund_amount),
            'total_users': total_users,
            'recent_users_count': recent_users_count,
            'trend_labels': trend_labels,
            'trend_revenue': trend_revenue,
            'trend_bookings': trend_bookings,
            'top_movies': top_movies,
            'theater_performance': theater_performance,
            'peak_hours': peak_hours,
        }
        return render(request, 'dashboard/admin_dashboard.html', context)


class ExportAnalyticsCSVView(StaffAdminRequiredMixin, View):
    """
    Exports analytics summary report as downloadable CSV.
    GET /dashboard/export-csv/
    """
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="CinePass_Analytics_Report.csv"'

        writer = csv.writer(response)
        writer.writerow(['Date', 'Confirmed Bookings', 'Tickets Sold', 'Gross Revenue (INR)', 'Refunded Amount (INR)'])

        daily_trends = Booking.objects.filter(
            status='CONFIRMED'
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            revenue=Sum('grand_total'),
            bookings=Count('id'),
            tickets=Sum('total_seats')
        ).order_by('-date')

        for row in daily_trends:
            if row['date']:
                ref_amt = Payment.objects.filter(
                    created_at__date=row['date'],
                    status='REFUNDED'
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

                writer.writerow([
                    row['date'].strftime('%Y-%m-%d'),
                    row['bookings'],
                    row['tickets'],
                    f"{row['revenue']:.2f}",
                    f"{ref_amt:.2f}"
                ])

        return response
