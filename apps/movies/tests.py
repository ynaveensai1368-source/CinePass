import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model

from movies.models import Genre, Language, Movie, RecentlyViewed
from theaters.models import City, Theater, Screen
from shows.models import Show
from bookings.models import Booking
from movies.recommendations import get_personalized_recommendations

User = get_user_model()

class MovieDiscoverySystemTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create User
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='Password123'
        )

        # Create Taxonomies
        self.lang = Language.objects.create(name='English', code='en')
        self.action = Genre.objects.create(name='Action')
        self.sci_fi = Genre.objects.create(name='Sci-Fi')

        # Create City, Theater, Screen
        self.city = City.objects.create(name='Metropolis', state='NY')
        self.theater = Theater.objects.create(name='Grand Cinema', city=self.city, address='123 Main St')
        self.screen = Screen.objects.create(theater=self.theater, name='Audi 1', total_seats=100)

        # Create Movies
        self.movie1 = Movie.objects.create(
            title='Inception',
            description='Mind bending thriller',
            language=self.lang,
            duration=148,
            release_date=datetime.date(2010, 7, 16),
            rating=8.8,
            popularity=95,
            poster_url='https://image.tmdb.org/t/p/w500/inception.jpg'
        )
        self.movie1.genres.add(self.action, self.sci_fi)

        self.movie2 = Movie.objects.create(
            title='Interstellar',
            description='Space exploration sci-fi',
            language=self.lang,
            duration=169,
            release_date=datetime.date(2014, 11, 7),
            rating=8.6,
            popularity=90,
            poster_url='https://image.tmdb.org/t/p/w500/interstellar.jpg'
        )
        self.movie2.genres.add(self.sci_fi)

        # Create Show
        self.show = Show.objects.create(
            movie=self.movie1,
            screen=self.screen,
            start_time=timezone.now() + datetime.timedelta(days=1),
            base_price=Decimal('15.00'),
            available_seats=50
        )

    def test_search_movies_case_insensitive(self):
        url = reverse('movies:discovery') + '?q=incEPTion'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inception')
        self.assertNotContains(response, 'Interstellar')

    def test_multi_filter_combination(self):
        url = f"{reverse('movies:discovery')}?genre={self.action.id}&city={self.city.id}&rating=8.0"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['movies']), 1)
        self.assertEqual(response.context['movies'][0], self.movie1)

    from unittest.mock import patch

    @patch('bookings.tasks.send_booking_email_task.apply_async')
    def test_ticket_booking_and_cancellation(self, mock_email):
        self.client.login(email='test@example.com', password='Password123')
        
        # Book 2 tickets
        book_url = reverse('bookings:book_tickets', kwargs={'show_id': self.show.id})
        response = self.client.post(book_url, {'seats_booked': 2})
        self.assertEqual(response.status_code, 302) # Redirect to history


        # Check seats deducted
        self.show.refresh_from_db()
        self.assertEqual(self.show.available_seats, 48)
        
        booking = Booking.objects.get(user=self.user, show=self.show)
        self.assertEqual(booking.total_seats, 2)

        # Cancel booking
        cancel_url = reverse('bookings:cancel_booking', kwargs={'booking_id': booking.id})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, 302)
        
        self.show.refresh_from_db()
        booking.refresh_from_db()
        self.assertEqual(self.show.available_seats, 50)
        self.assertEqual(booking.status, 'CANCELLED')

    def test_personalized_recommendation_engine(self):
        # Book Action movie
        Booking.objects.create(user=self.user, show=self.show, total_seats=1, total_price=Decimal('15.00'), status='CONFIRMED')

        recs = get_personalized_recommendations(user=self.user, limit=5)
        # Should recommend Interstellar (Sci-Fi affinity) and exclude Inception (already booked)
        self.assertNotIn(self.movie1, recs)
        self.assertIn(self.movie2, recs)

    def test_movie_suggestions_api(self):
        url = reverse('movies:api_suggestions') + '?q=inc'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertGreaterEqual(data['count'], 1)
        titles = [item['title'] for item in data['suggestions']]
        self.assertIn('Inception', titles)
        self.assertNotIn('Interstellar', titles)

    def test_home_view_movie_context(self):
        url = reverse('movies:home')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('hero_movies', response.context)
        self.assertIn('popular_movies', response.context)
        self.assertIn('recommended_movies', response.context)
        self.assertGreaterEqual(len(response.context['popular_movies']), 1)
        self.assertGreaterEqual(len(response.context['recommended_movies']), 1)
