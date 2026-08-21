import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model

from movies.models import Movie, Genre, Language
from theaters.models import City, Theater, Screen, Seat
from shows.models import Show, ShowSeat, SeatReservation
from bookings.models import Booking, BookingSeat
from bookings.utils import generate_pdf_ticket, generate_qr_code_bytes, generate_ticket_signature_token, verify_ticket_signature_token

User = get_user_model()


class BookingsSystemTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='bookinguser',
            email='bookinguser@example.com',
            password='Password123'
        )
        self.lang = Language.objects.create(name='English', code='en')
        self.genre = Genre.objects.create(name='Action')
        self.city = City.objects.create(name='Metropolis', state='NY')
        self.theater = Theater.objects.create(name='Grand Cinema', city=self.city, address='123 Main St')
        self.screen = Screen.objects.create(theater=self.theater, name='Audi 1', total_seats=60)
        self.seat = Seat.objects.create(screen=self.screen, row='A', number=1, seat_type='REGULAR')

        self.movie = Movie.objects.create(
            title='Inception',
            description='Thriller',
            language=self.lang,
            duration=148,
            release_date=datetime.date(2010, 7, 16),
            rating=8.8,
            popularity=95,
            poster_url='https://image.tmdb.org/t/p/w500/inception.jpg'
        )
        self.movie.genres.add(self.genre)

        self.show = Show.objects.create(
            movie=self.movie,
            screen=self.screen,
            start_time=timezone.now() + datetime.timedelta(days=1),
            base_price=Decimal('200.00'),
            available_seats=60
        )

        self.booking = Booking.objects.create(
            user=self.user,
            show=self.show,
            total_seats=1,
            total_price=Decimal('200.00'),
            convenience_fee=Decimal('30.00'),
            grand_total=Decimal('230.00'),
            status='CONFIRMED'
        )
        self.booking_seat = BookingSeat.objects.create(
            booking=self.booking,
            seat=self.seat,
            price=Decimal('200.00')
        )

    def test_pdf_ticket_generation(self):
        pdf_bytes = generate_pdf_ticket(self.booking)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_qr_code_and_signature_token(self):
        qr_bytes = generate_qr_code_bytes(self.booking)
        self.assertIsNotNone(qr_bytes)
        token = generate_ticket_signature_token(self.booking)
        is_valid, payload = verify_ticket_signature_token(token)
        self.assertTrue(is_valid)
        self.assertEqual(payload['booking_id'], self.booking.id)

    def test_download_ticket_pdf_view(self):
        self.client.login(email='bookinguser@example.com', password='Password123')
        url = reverse('bookings:download_ticket', kwargs={'booking_id': self.booking.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_verify_ticket_view(self):
        token = generate_ticket_signature_token(self.booking)
        url = reverse('bookings:verify_ticket', kwargs={'token': token})
        response = self.client.get(url, HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'VALID')
        self.assertEqual(data['booking_number'], self.booking.booking_number)
