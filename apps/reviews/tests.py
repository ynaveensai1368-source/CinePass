import datetime
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from movies.models import Movie, Language
from reviews.models import Review, ReviewReport
from theaters.models import City, Theater, Screen
from shows.models import Show
from bookings.models import Booking

User = get_user_model()

class ReviewModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='reviewer', email='reviewer@example.com', password='password123')
        self.other_user = User.objects.create_user(username='other', email='other@example.com', password='password123')
        self.language = Language.objects.create(name='English', code='en')
        self.movie = Movie.objects.create(
            title='Interstellar', description='Space exploration drama', release_date='2014-11-07', duration=169, language=self.language
        )
        self.city = City.objects.create(name='Metropolis')
        self.theater = Theater.objects.create(name='Cine 1', city=self.city)
        self.screen = Screen.objects.create(theater=self.theater, name='Audi 1', total_seats=50)
        self.show = Show.objects.create(
            movie=self.movie, screen=self.screen,
            start_time=timezone.now() - datetime.timedelta(hours=3),
            base_price=200
        )
        self.booking = Booking.objects.create(user=self.user, show=self.show, total_seats=1, total_price=200, grand_total=230, status='CONFIRMED')

    def test_str_with_valid_user_and_movie(self):
        review = Review.objects.create(user=self.user, movie=self.movie, rating=9, comment='Amazing movie!')
        expected_str = f"Review by reviewer@example.com for Interstellar (9/10)"
        self.assertEqual(str(review), expected_str)

    def test_review_reporting_api(self):
        review = Review.objects.create(user=self.user, movie=self.movie, rating=9, comment='Awesome')

        client_other = Client()
        client_other.force_login(self.other_user)

        # Other user reports review -> Success
        response = client_other.post(
            f'/reviews/api/review/{review.id}/report/',
            data={'reason': 'Inappropriate language'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))

        # Duplicate report -> Fails
        response2 = client_other.post(
            f'/reviews/api/review/{review.id}/report/',
            data={'reason': 'Duplicate report'},
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 400)
        self.assertEqual(response2.json().get('code'), 'DUPLICATE_REPORT')

    def test_self_report_prevention(self):
        review = Review.objects.create(user=self.user, movie=self.movie, rating=9, comment='Awesome')
        client_owner = Client()
        client_owner.force_login(self.user)

        # Owner reporting own review -> Fails
        response = client_owner.post(
            f'/reviews/api/review/{review.id}/report/',
            data={'reason': 'Self report'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json().get('code'), 'SELF_REPORT_DENIED')
