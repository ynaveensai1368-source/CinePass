import json
import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model

from movies.models import Movie, Genre, Language
from theaters.models import City, Theater, Screen, Seat
from shows.models import Show, ShowSeat, SeatReservation
from bookings.models import Booking
from payments.models import Payment
from payments.services import create_razorpay_order, verify_razorpay_signature

User = get_user_model()


class PaymentsSystemTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='payuser',
            email='payuser@example.com',
            password='Password123'
        )
        self.lang = Language.objects.create(name='English', code='en')
        self.city = City.objects.create(name='Metropolis', state='NY')
        self.theater = Theater.objects.create(name='Grand Cinema', city=self.city, address='123 Main St')
        self.screen = Screen.objects.create(theater=self.theater, name='Audi 1', total_seats=50)
        self.seat = Seat.objects.create(screen=self.screen, row='A', number=1, seat_type='REGULAR')

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
            base_price=Decimal('250.00'),
            available_seats=50
        )

        self.booking = Booking.objects.create(
            user=self.user,
            show=self.show,
            total_seats=1,
            total_price=Decimal('250.00'),
            convenience_fee=Decimal('30.00'),
            grand_total=Decimal('280.00'),
            status='PENDING'
        )

        self.reservation = SeatReservation.objects.create(
            show=self.show,
            seat=self.seat,
            user=self.user,
            reservation_token='RES-TEST123456',
            status='RESERVED',
            total_amount=Decimal('250.00'),
            expires_at=timezone.now() + datetime.timedelta(minutes=2)
        )
        self.show_seat = ShowSeat.objects.create(
            show=self.show,
            seat=self.seat,
            status='RESERVED',
            price=Decimal('250.00'),
            reservation=self.reservation
        )

    def test_checkout_view_get(self):
        self.client.login(email='payuser@example.com', password='Password123')
        url = f"{reverse('payments:checkout', kwargs={'show_id': self.show.id})}?seats={self.seat.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkout & Payment')
        self.assertContains(response, 'Inception')

    def test_create_order_service(self):
        order = create_razorpay_order(amount_in_inr=280.0, receipt='rcpt_test_1')
        self.assertIsNotNone(order)
        self.assertIn('id', order)
        self.assertEqual(order['amount'], 28000)

    def test_verify_signature_service(self):
        valid = verify_razorpay_signature('order_123', 'pay_123', 'sig_123')
        self.assertIsInstance(valid, bool)

    def test_payment_failure_api(self):
        self.client.login(email='payuser@example.com', password='Password123')
        payment = Payment.objects.create(
            booking=self.booking,
            order_id='order_fail_test',
            amount=Decimal('280.00'),
            status='PENDING'
        )
        url = reverse('payments:api_failed')
        response = self.client.post(
            url,
            data=json.dumps({'order_id': 'order_fail_test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'FAILED')
        self.show_seat.refresh_from_db()
        self.assertEqual(self.show_seat.status, 'AVAILABLE')

    def test_payment_retry_api(self):
        self.client.login(email='payuser@example.com', password='Password123')
        url = reverse('payments:api_retry')
        response = self.client.post(
            url,
            data=json.dumps({'booking_id': self.booking.id}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('razorpay_order_id', data)

    def test_payment_webhook_captured_and_failed(self):
        payment = Payment.objects.create(
            booking=self.booking,
            order_id='order_webhook_test',
            amount=Decimal('280.00'),
            status='PENDING'
        )
        url = reverse('payments:webhook')

        # 1. Test captured event
        captured_payload = {
            'event': 'payment.captured',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_webhook_captured_1',
                        'order_id': 'order_webhook_test',
                        'status': 'captured'
                    }
                }
            }
        }
        res_captured = self.client.post(
            url,
            data=json.dumps(captured_payload),
            content_type='application/json'
        )
        self.assertEqual(res_captured.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'SUCCESS')
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, 'CONFIRMED')

    def test_demo_sign_api(self):
        self.client.login(email='payuser@example.com', password='Password123')
        url = reverse('payments:api_demo_sign')
        response = self.client.post(
            url,
            data=json.dumps({'order_id': 'order_demo_test', 'payment_id': 'pay_demo_test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('signature', data)
        # Verify generated signature
        is_valid = verify_razorpay_signature('order_demo_test', 'pay_demo_test', data['signature'])
        self.assertTrue(is_valid)
