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

        # Create Movies (Current Active Releases)
        today = timezone.now().date()
        self.movie1 = Movie.objects.create(
            title='Inception',
            description='Mind bending thriller',
            language=self.lang,
            duration=148,
            release_date=today,
            rating=8.8,
            popularity=95,
            category='now_playing',
            poster_url='https://image.tmdb.org/t/p/w500/inception.jpg'
        )
        self.movie1.genres.add(self.action, self.sci_fi)

        self.movie2 = Movie.objects.create(
            title='Interstellar',
            description='Space exploration sci-fi',
            language=self.lang,
            duration=169,
            release_date=today,
            rating=8.6,
            popularity=90,
            category='now_playing',
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

    def test_location_context_and_set_api(self):
        """Test persistent location selection API and context processor."""
        hyd_city = City.objects.create(name='Hyderabad', state='Telangana', slug='hyderabad')
        chn_city = City.objects.create(name='Chennai', state='Tamil Nadu', slug='chennai')

        # 1. Test set_location_api
        res = self.client.post(reverse('api_set_location'), {'city_id': hyd_city.id})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['city']['name'], 'Hyderabad')

        # 2. Verify session persistence on HomeView
        home_res = self.client.get(reverse('movies:home'))
        self.assertEqual(home_res.status_code, 200)
        self.assertEqual(home_res.context['current_city'].id, hyd_city.id)

        # 3. Change location to Chennai
        res2 = self.client.post(reverse('api_set_location'), {'city_id': chn_city.id})
        self.assertEqual(res2.status_code, 200)
        home_res2 = self.client.get(reverse('movies:home'))
        self.assertEqual(home_res2.context['current_city'].id, chn_city.id)

    def test_geolocation_detect_api(self):
        """Test GPS coordinate Haversine nearest city resolution."""
        hyd = City.objects.create(name='Hyderabad', state='Telangana', slug='hyderabad')
        chn = City.objects.create(name='Chennai', state='Tamil Nadu', slug='chennai')

        # Coordinates near Hyderabad (Secunderabad coords)
        res_hyd = self.client.get(reverse('api_detect_location') + '?lat=17.44&lng=78.50')
        self.assertEqual(res_hyd.status_code, 200)
        data_hyd = res_hyd.json()
        self.assertEqual(data_hyd['status'], 'success')
        self.assertEqual(data_hyd['city']['id'], hyd.id)

        # Coordinates near Chennai
        res_chn = self.client.get(reverse('api_detect_location') + '?lat=13.05&lng=80.25')
        self.assertEqual(res_chn.status_code, 200)
        data_chn = res_chn.json()
        self.assertEqual(data_chn['status'], 'success')
        self.assertEqual(data_chn['city']['id'], chn.id)

    def test_location_and_regional_language_recommendations(self):
        """Test BookMyShow-style regional language prioritization by city."""
        telugu_lang = Language.objects.create(name='Telugu', code='te')
        tamil_lang = Language.objects.create(name='Tamil', code='ta')

        hyd_city = City.objects.create(name='Hyderabad', state='Telangana', slug='hyderabad')
        chn_city = City.objects.create(name='Chennai', state='Tamil Nadu', slug='chennai')

        hyd_theater = Theater.objects.create(name='AMB Cinemas', city=hyd_city, address='Gachibowli')
        chn_theater = Theater.objects.create(name='SPI Sathyam', city=chn_city, address='Royapettah')

        hyd_screen = Screen.objects.create(theater=hyd_theater, name='Screen 1', total_seats=100)
        chn_screen = Screen.objects.create(theater=chn_theater, name='Screen 1', total_seats=100)

        today = timezone.now().date()
        telugu_movie = Movie.objects.create(
            title='Telugu Blockbuster',
            language=telugu_lang,
            duration=150,
            release_date=today,
            popularity=80,
            category='now_playing',
            rating=8.5
        )
        tamil_movie = Movie.objects.create(
            title='Tamil Blockbuster',
            language=tamil_lang,
            duration=150,
            release_date=today,
            popularity=80,
            category='now_playing',
            rating=8.5
        )

        Show.objects.create(movie=telugu_movie, screen=hyd_screen, start_time=timezone.now() + datetime.timedelta(days=1), base_price=Decimal('200'), available_seats=80)
        Show.objects.create(movie=tamil_movie, screen=chn_screen, start_time=timezone.now() + datetime.timedelta(days=1), base_price=Decimal('200'), available_seats=80)

        # In Hyderabad: Telugu movie must rank higher than Tamil movie
        hyd_recs = get_personalized_recommendations(city=hyd_city, limit=4)
        self.assertIn(telugu_movie, hyd_recs)
        telugu_idx = hyd_recs.index(telugu_movie)
        if tamil_movie in hyd_recs:
            tamil_idx = hyd_recs.index(tamil_movie)
            self.assertLess(telugu_idx, tamil_idx)

        # In Chennai: Tamil movie must rank higher than Telugu movie
        chn_recs = get_personalized_recommendations(city=chn_city, limit=4)
        self.assertIn(tamil_movie, chn_recs)
        tamil_idx2 = chn_recs.index(tamil_movie)
        if telugu_movie in chn_recs:
            telugu_idx2 = chn_recs.index(telugu_movie)
            self.assertLess(tamil_idx2, telugu_idx2)

    def test_coupled_theaters_by_city_api(self):
        """Test API returning theaters filtered by city for dynamic dropdown cascading."""
        hyd_city = City.objects.create(name='Hyderabad', state='Telangana')
        t1 = Theater.objects.create(name='Prasads Multiplex', city=hyd_city, address='Necklace Rd')
        
        res = self.client.get(reverse('api_theaters_by_city') + f'?city_id={hyd_city.id}')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        theater_names = [t['name'] for t in data['theaters']]
        self.assertIn('Prasads Multiplex', theater_names)

    def test_explore_empty_state_messaging(self):
        """Test informative empty state when city and language combination yields zero shows."""
        french_lang = Language.objects.create(name='French', code='fr')
        hyd_city = City.objects.create(name='Hyderabad', state='Telangana')

        res = self.client.get(reverse('movies:discovery') + f'?city={hyd_city.id}&language={french_lang.id}')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['movie_count'], 0)
        self.assertContains(res, 'No French Movies in Hyderabad')


