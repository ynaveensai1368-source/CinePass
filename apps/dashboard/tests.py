import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model

from movies.models import Movie, Language
from theaters.models import City, Theater, Screen
from shows.models import Show
from bookings.models import Booking
from payments.models import Payment

User = get_user_model()


class DashboardAnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            username='adminuser',
            email='admin@example.com',
            password='Password123'
        )
        self.regular_user = User.objects.create_user(
            username='regularuser',
            email='regular@example.com',
            password='Password123'
        )

        self.lang = Language.objects.create(name='English', code='en')
        self.city = City.objects.create(name='Metropolis', state='NY')
        self.theater = Theater.objects.create(name='Grand Cinema', city=self.city, address='123 Main St')
        self.screen = Screen.objects.create(theater=self.theater, name='Audi 1', total_seats=100)

        self.movie = Movie.objects.create(
            title='Inception',
            description='Mind bending thriller',
            language=self.lang,
            duration=148,
            release_date=datetime.date(2010, 7, 16),
            rating=8.8,
            popularity=95,
            poster_url='https://image.tmdb.org/t/p/w500/inception.jpg'
        )

        self.show = Show.objects.create(
            movie=self.movie,
            screen=self.screen,
            start_time=timezone.now() + datetime.timedelta(days=1),
            base_price=Decimal('200.00'),
            available_seats=100
        )

        self.booking = Booking.objects.create(
            user=self.regular_user,
            show=self.show,
            total_seats=2,
            total_price=Decimal('400.00'),
            convenience_fee=Decimal('30.00'),
            grand_total=Decimal('430.00'),
            status='CONFIRMED'
        )

        self.payment = Payment.objects.create(
            booking=self.booking,
            order_id='order_dash_test',
            payment_id='pay_dash_test',
            amount=Decimal('430.00'),
            status='SUCCESS'
        )

    def test_admin_dashboard_security_access(self):
        # Regular user denied
        self.client.login(email='regular@example.com', password='Password123')
        url = reverse('dashboard:admin_dashboard')
        res_regular = self.client.get(url)
        self.assertEqual(res_regular.status_code, 403)

        # Admin user allowed
        self.client.login(email='admin@example.com', password='Password123')
        res_admin = self.client.get(url)
        self.assertEqual(res_admin.status_code, 200)
        self.assertEqual(res_admin.context['total_bookings_count'], 1)
        self.assertEqual(res_admin.context['total_revenue'], 430.0)

    def test_dashboard_period_filters(self):
        self.client.login(email='admin@example.com', password='Password123')
        url = reverse('dashboard:admin_dashboard')
        for period in ['today', '7days', '30days', 'this_month', 'this_year']:
            res = self.client.get(f"{url}?period={period}")
            self.assertEqual(res.status_code, 200)

    def test_dashboard_csv_export(self):
        self.client.login(email='admin@example.com', password='Password123')
        url = reverse('dashboard:export_csv')
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv')
        self.assertIn('attachment;', res['Content-Disposition'])
