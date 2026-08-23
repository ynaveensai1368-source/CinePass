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

    def test_image_url_normalization_and_fallback(self):
        from movies.utils.images import normalize_image_url, FALLBACK_POSTER

        # 1. Relative TMDb path
        self.assertEqual(
            normalize_image_url('/abc123xyz.jpg', size='w500'),
            'https://image.tmdb.org/t/p/w500/abc123xyz.jpg'
        )

        # 2. Insecure HTTP upgrade
        self.assertEqual(
            normalize_image_url('http://image.tmdb.org/t/p/w500/abc.jpg'),
            'https://image.tmdb.org/t/p/w500/abc.jpg'
        )

        # 3. Empty / None fallback
        self.assertEqual(normalize_image_url(None), FALLBACK_POSTER)
        self.assertEqual(normalize_image_url(''), FALLBACK_POSTER)

        # 4. Movie model properties
        test_m = Movie.objects.create(
            title='Test Poster Movie',
            description='Test description',
            language=self.lang,
            duration=120,
            release_date=datetime.date(2024, 1, 1),
            poster_url='/testposter.jpg',
            backdrop_url='/testbackdrop.jpg'
        )
        self.assertEqual(test_m.get_poster_url, 'https://image.tmdb.org/t/p/w500/testposter.jpg')
        self.assertEqual(test_m.get_backdrop_url, 'https://image.tmdb.org/t/p/w1280/testbackdrop.jpg')

        # Fallback when poster_url is empty
        empty_m = Movie.objects.create(
            title='Empty Poster Movie',
            description='Test description',
            language=self.lang,
            duration=120,
            release_date=datetime.date(2024, 1, 1),
            poster_url='',
            backdrop_url=''
        )
        self.assertEqual(empty_m.get_poster_url, FALLBACK_POSTER)
        self.assertEqual(empty_m.get_backdrop_url, FALLBACK_POSTER)

    def test_movie_detail_grouped_theaters_and_showtimes(self):
        """Verify that movie details view groups showtimes hierarchically by Theater and Screen."""
        # Create a second screen in the same theater and a second show
        screen2 = Screen.objects.create(theater=self.theater, name='IMAX Laser Screen 2', screen_type='IMAX_3D', total_seats=80)
        show2 = Show.objects.create(
            movie=self.movie1,
            screen=screen2,
            start_time=timezone.now() + datetime.timedelta(days=1, hours=3),
            base_price=Decimal('25.00'),
            available_seats=80
        )

        url = reverse('movies:detail', kwargs={'slug': self.movie1.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check context variables
        self.assertIn('grouped_theaters', response.context)
        self.assertIn('available_dates', response.context)
        self.assertIn('available_cities', response.context)

        grouped = response.context['grouped_theaters']
        self.assertEqual(len(grouped), 1)  # Only 1 unique theater
        self.assertEqual(grouped[0]['theater'], self.theater)
        self.assertEqual(grouped[0]['city'], self.city)
        self.assertEqual(len(grouped[0]['screens']), 2)  # 2 distinct screens

        # Verify only Movie 1 showtimes are shown (not another movie)
        other_movie = self.movie2
        other_show = Show.objects.create(
            movie=other_movie,
            screen=self.screen,
            start_time=timezone.now() + datetime.timedelta(days=1),
            base_price=Decimal('20.00'),
            available_seats=50
        )
        response_other = self.client.get(reverse('movies:detail', kwargs={'slug': other_movie.slug}))
        self.assertEqual(response_other.status_code, 200)
        other_grouped = response_other.context['grouped_theaters']
        self.assertEqual(len(other_grouped), 1)
        # Ensure other movie page only lists other_show
        shows_in_other = other_grouped[0]['screens'][0]['shows']
        self.assertEqual(len(shows_in_other), 1)
        self.assertEqual(shows_in_other[0].id, other_show.id)

    def test_movie_trailer_properties_and_isolation(self):
        """Test strict movie-to-trailer relationship and property methods."""
        # 1. Movie with standard YouTube Watch URL
        movie_with_trailer = Movie.objects.create(
            title='Trailer Test Movie 1',
            description='Test description',
            language=self.lang,
            duration=120,
            release_date=datetime.date(2025, 1, 1),
            trailer_url='https://www.youtube.com/watch?v=8TZMtslA3UY'
        )
        self.assertEqual(movie_with_trailer.trailer_youtube_key, '8TZMtslA3UY')
        self.assertTrue(movie_with_trailer.has_trailer)
        self.assertEqual(movie_with_trailer.get_clean_trailer_url, 'https://www.youtube.com/embed/8TZMtslA3UY?autoplay=1')
        self.assertEqual(movie_with_trailer.get_youtube_watch_url, 'https://www.youtube.com/watch?v=8TZMtslA3UY')

        # 2. Movie with YouTube Embed URL
        movie_with_embed = Movie.objects.create(
            title='Trailer Test Movie 2',
            description='Test description',
            language=self.lang,
            duration=115,
            release_date=datetime.date(2025, 2, 1),
            trailer_url='https://www.youtube.com/embed/Mzw2ttJD2qQ?autoplay=1'
        )
        self.assertEqual(movie_with_embed.trailer_youtube_key, 'Mzw2ttJD2qQ')
        self.assertTrue(movie_with_embed.has_trailer)
        self.assertEqual(movie_with_embed.get_clean_trailer_url, 'https://www.youtube.com/embed/Mzw2ttJD2qQ?autoplay=1')
        self.assertEqual(movie_with_embed.get_youtube_watch_url, 'https://www.youtube.com/watch?v=Mzw2ttJD2qQ')

        # 3. Movie with NO trailer
        movie_no_trailer = Movie.objects.create(
            title='No Trailer Movie',
            description='Test description',
            language=self.lang,
            duration=100,
            release_date=datetime.date(2025, 3, 1),
            trailer_url=''
        )
        self.assertEqual(movie_no_trailer.trailer_youtube_key, '')
        self.assertFalse(movie_no_trailer.has_trailer)
        self.assertEqual(movie_no_trailer.get_clean_trailer_url, '')
        self.assertEqual(movie_no_trailer.get_youtube_watch_url, '')

        # 4. Ensure distinct movies have different trailer keys
        self.assertNotEqual(movie_with_trailer.trailer_youtube_key, movie_with_embed.trailer_youtube_key)

    def test_movie_detail_view_trailer_context(self):
        """Test detail page renders trailer attributes for movie with trailer vs movie without."""
        m_trailer = Movie.objects.create(
            title='Detail Trailer Movie',
            description='Test description',
            language=self.lang,
            duration=120,
            release_date=datetime.date(2025, 1, 1),
            trailer_url='https://www.youtube.com/watch?v=8TZMtslA3UY'
        )
        res = self.client.get(reverse('movies:detail', kwargs={'slug': m_trailer.slug}))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['has_trailer'])
        self.assertEqual(res.context['trailer_youtube_key'], '8TZMtslA3UY')
        self.assertContains(res, 'Watch Official Trailer')

        m_no_trailer = Movie.objects.create(
            title='Detail No Trailer Movie',
            description='Test description',
            language=self.lang,
            duration=100,
            release_date=datetime.date(2025, 3, 1),
            trailer_url=''
        )
        res_no = self.client.get(reverse('movies:detail', kwargs={'slug': m_no_trailer.slug}))
        self.assertEqual(res_no.status_code, 200)
        self.assertFalse(res_no.context['has_trailer'])
        self.assertEqual(res_no.context['trailer_youtube_key'], '')
        self.assertContains(res_no, 'Trailer Unavailable')

