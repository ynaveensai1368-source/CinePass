import datetime
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from django.test import TestCase, TransactionTestCase, Client
from django.utils import timezone
from django.contrib.auth import get_user_model

from movies.models import Genre, Language, Movie
from theaters.models import City, Theater, Screen, Seat
from shows.models import Show, SeatReservation, ShowSeat
from shows.tasks import expire_seat_reservations

User = get_user_model()


class SeatConcurrencyTests(TransactionTestCase):
    """
    Tests atomic row-level concurrency locking when two users attempt to reserve
    the exact same seat simultaneously.
    """
    reset_sequences = True

    def setUp(self):
        self.user_a = User.objects.create_user(username='usera', email='usera@example.com', password='Password123')
        self.user_b = User.objects.create_user(username='userb', email='userb@example.com', password='Password123')

        self.lang = Language.objects.create(name='English', code='en')
        self.movie = Movie.objects.create(
            title='Inception', description='Mind bending thriller', language=self.lang,
            duration=148, release_date=datetime.date(2010, 7, 16), rating=8.8
        )
        self.city = City.objects.create(name='Metropolis')
        self.theater = Theater.objects.create(name='Grand Cinema', city=self.city)
        self.screen = Screen.objects.create(theater=self.theater, name='Audi 1', total_seats=100)
        self.seat = Seat.objects.create(screen=self.screen, row='A', number=1, seat_type='REGULAR')

        self.show = Show.objects.create(
            movie=self.movie, screen=self.screen,
            start_time=timezone.now() + datetime.timedelta(days=1),
            base_price=Decimal('200.00'), available_seats=100
        )
        self.show_seat = ShowSeat.objects.create(show=self.show, seat=self.seat, price=Decimal('200.00'), status='AVAILABLE')

    def test_concurrent_seat_reservation_locking(self):
        """
        User A reserves seat A1. Immediately following, User B attempts to reserve seat A1.
        Expected: User A -> SUCCESS (200 OK), User B -> SEAT_UNAVAILABLE (409 Conflict).
        Database Result: Exactly ONE active reservation record.
        """
        client_a = Client()
        client_a.force_login(self.user_a)

        client_b = Client()
        client_b.force_login(self.user_b)

        # User A reserves seat A1
        resp_a = client_a.post(
            f'/shows/api/{self.show.id}/seats/reserve/',
            data={'seat_ids': [self.seat.id]},
            content_type='application/json'
        )
        self.assertEqual(resp_a.status_code, 200)
        self.assertTrue(resp_a.json().get('success'))

        # User B attempts to reserve the exact same seat A1
        resp_b = client_b.post(
            f'/shows/api/{self.show.id}/seats/reserve/',
            data={'seat_ids': [self.seat.id]},
            content_type='application/json'
        )
        self.assertEqual(resp_b.status_code, 409)
        self.assertFalse(resp_b.json().get('success'))
        self.assertEqual(resp_b.json().get('code'), 'SEAT_UNAVAILABLE')

        # Ensure database has exactly one active reservation record
        active_reservations = SeatReservation.objects.filter(show=self.show, seat=self.seat, status__in=['ACTIVE', 'RESERVED'])
        self.assertEqual(active_reservations.count(), 1)


class SeatReservationExpiryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testusr', email='testusr@example.com', password='Password123')
        self.lang = Language.objects.create(name='English', code='en')
        self.movie = Movie.objects.create(title='Avatar', description='Desc', language=self.lang, duration=160, release_date=datetime.date(2009, 12, 18))
        self.city = City.objects.create(name='Metropolis')
        self.theater = Theater.objects.create(name='Cinema 1', city=self.city)
        self.screen = Screen.objects.create(theater=self.theater, name='Audi 1', total_seats=50)
        self.seat = Seat.objects.create(screen=self.screen, row='B', number=2, seat_type='REGULAR')
        self.show = Show.objects.create(movie=self.movie, screen=self.screen, start_time=timezone.now() + datetime.timedelta(days=1), base_price=Decimal('150.00'))
        self.show_seat = ShowSeat.objects.create(show=self.show, seat=self.seat, price=Decimal('150.00'), status='AVAILABLE')

    def test_reservation_expiration_after_2_minutes(self):
        expired_time = timezone.now() - datetime.timedelta(minutes=3)
        res = SeatReservation.objects.create(
            show=self.show,
            seat=self.seat,
            user=self.user,
            reservation_token='TEST-TOKEN-123',
            status='ACTIVE',
            expires_at=expired_time
        )
        self.show_seat.status = 'RESERVED'
        self.show_seat.reservation = res
        self.show_seat.save()

        self.assertFalse(res.is_active())

        # Requesting API should clean it up
        response = self.client.get(f'/shows/api/{self.show.id}/seats/')
        self.assertEqual(response.status_code, 200)

        res.refresh_from_db()
        self.assertEqual(res.status, 'EXPIRED')

        self.show_seat.refresh_from_db()
        self.assertEqual(self.show_seat.status, 'AVAILABLE')

    def test_celery_expiration_task(self):
        expired_time = timezone.now() - datetime.timedelta(minutes=5)
        res = SeatReservation.objects.create(
            show=self.show,
            seat=self.seat,
            user=self.user,
            reservation_token='TASK-TOKEN-456',
            status='ACTIVE',
            expires_at=expired_time
        )
        self.show_seat.status = 'RESERVED'
        self.show_seat.reservation = res
        self.show_seat.save()

        cleaned_count = expire_seat_reservations()
        self.assertEqual(cleaned_count, 1)

        res.refresh_from_db()
        self.assertEqual(res.status, 'EXPIRED')

        self.show_seat.refresh_from_db()
        self.assertEqual(self.show_seat.status, 'AVAILABLE')
