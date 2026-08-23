import random
import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from movies.models import Genre, Language, Movie, Cast, Poster
from theaters.models import City, Theater, Screen, Seat
from shows.models import Show
from bookings.models import Booking, BookingSeat
from payments.models import Payment
from reviews.models import Review

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds realistic demo data for CinePass movie booking platform.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting CinePass demo data seeding..."))

        # 1. Languages
        languages_data = [
            {'name': 'English', 'code': 'en'},
            {'name': 'Hindi', 'code': 'hi'},
            {'name': 'Telugu', 'code': 'te'},
            {'name': 'Tamil', 'code': 'ta'},
            {'name': 'Malayalam', 'code': 'ml'},
        ]
        languages = []
        for ldata in languages_data:
            lang, _ = Language.objects.get_or_create(code=ldata['code'], defaults={'name': ldata['name']})
            languages.append(lang)

        # 2. Genres
        genres_list = ['Action', 'Sci-Fi', 'Drama', 'Comedy', 'Thriller', 'Romance', 'Adventure', 'Horror', 'Animation']
        genres = []
        for gname in genres_list:
            genre, _ = Genre.objects.get_or_create(name=gname)
            genres.append(genre)

        # 3. Cities & Theaters
        cities_data = [
            {'name': 'Hyderabad', 'state': 'Telangana'},
            {'name': 'Mumbai', 'state': 'Maharashtra'},
            {'name': 'Bengaluru', 'state': 'Karnataka'},
            {'name': 'Delhi-NCR', 'state': 'Delhi'},
        ]
        cities = []
        theaters = []
        for cdata in cities_data:
            city, _ = City.objects.get_or_create(name=cdata['name'], defaults={'state': cdata['state']})
            cities.append(city)

            # Create 2 theaters per city
            for t_idx in range(1, 3):
                t_name = f"PVR Cineplex {city.name} {t_idx}"
                theater, _ = Theater.objects.get_or_create(
                    name=t_name,
                    city=city,
                    defaults={'address': f"Building {t_idx}, Main Road, {city.name}"}
                )
                theaters.append(theater)

                # Create 2 Screens per Theater
                for s_idx in range(1, 3):
                    screen, _ = Screen.objects.get_or_create(
                        theater=theater,
                        name=f"Audi {s_idx}",
                        defaults={'screen_type': 'IMAX_3D' if s_idx == 1 else '2D', 'total_seats': 40}
                    )

                    # Create Seats for Screen (Rows A-D, 1-10)
                    seats = []
                    for row_char in ['A', 'B', 'C', 'D']:
                        for num in range(1, 11):
                            seat_type = 'REGULAR' if row_char in ['A', 'B'] else ('PREMIUM' if row_char == 'C' else 'RECLINER')
                            if not Seat.objects.filter(screen=screen, row=row_char, number=num).exists():
                                seats.append(Seat(
                                    screen=screen,
                                    row=row_char,
                                    number=num,
                                    seat_type=seat_type
                                ))
                    if seats:
                        Seat.objects.bulk_create(seats)

        # 4. Movies
        from movies.utils.tmdb import get_movie_trailer_data

        movies_data = [
            {
                'tmdb_id': 693134,
                'title': 'Dune: Part Two',
                'description': 'Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.',
                'duration': 166,
                'release_date': datetime.date(2024, 3, 1),
                'rating': Decimal('8.6'),
                'popularity': 98,
                'category': 'popular',
                'poster_url': 'https://image.tmdb.org/t/p/w500/1pdfLPoL6VFi8283vFhMBmWRjJw.jpg',
                'genres': ['Sci-Fi', 'Adventure', 'Action']
            },
            {
                'tmdb_id': 872585,
                'title': 'Oppenheimer',
                'description': 'The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb.',
                'duration': 180,
                'release_date': datetime.date(2023, 7, 21),
                'rating': Decimal('8.9'),
                'popularity': 95,
                'category': 'top_rated',
                'poster_url': 'https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGvC271sC21.jpg',
                'genres': ['Drama', 'Thriller']
            },
            {
                'tmdb_id': 792307,
                'title': 'Kalki 2898 AD',
                'description': 'A modern avatar of Vishnu descends to Earth to protect humanity against evil forces in a post-apocalyptic world.',
                'duration': 180,
                'release_date': datetime.date(2024, 6, 27),
                'rating': Decimal('8.2'),
                'popularity': 92,
                'category': 'now_playing',
                'poster_url': 'https://image.tmdb.org/t/p/w500/61c8vAUp1YtT2P2q44S0Yl90JjL.jpg',
                'genres': ['Action', 'Sci-Fi']
            },
        ]

        created_movies = []
        for mdata in movies_data:
            genres_list = mdata.pop('genres', [])
            tmdb_id = mdata.get('tmdb_id')
            trailer_url = ''
            if tmdb_id:
                tdata = get_movie_trailer_data(tmdb_id, title=mdata['title'])
                if tdata and tdata.get('embed_url'):
                    trailer_url = tdata['embed_url']
            mdata['trailer_url'] = trailer_url

            movie, _ = Movie.objects.get_or_create(
                title=mdata['title'],
                defaults={
                    'tmdb_id': tmdb_id,
                    'description': mdata['description'],
                    'duration': mdata['duration'],
                    'release_date': mdata['release_date'],
                    'rating': mdata['rating'],
                    'popularity': mdata['popularity'],
                    'category': mdata['category'],
                    'language': languages[0],
                    'trailer_url': trailer_url,
                    'poster_url': mdata['poster_url'],
                }
            )
            if not movie.trailer_url and trailer_url:
                movie.trailer_url = trailer_url
                movie.save(update_fields=['trailer_url'])
            for gname in genres_list:
                gobj = next((g for g in genres if g.name == gname), None)
                if gobj:
                    movie.genres.add(gobj)
            created_movies.append(movie)

        # 5. Shows
        shows = []
        all_screens = Screen.objects.all()
        now = timezone.now()
        for movie in created_movies:
            for screen in all_screens[:4]:
                for day_offset in range(1, 4):
                    start_time = now + datetime.timedelta(days=day_offset, hours=random.choice([14, 18, 21]))
                    show, _ = Show.objects.get_or_create(
                        screen=screen,
                        start_time=start_time,
                        defaults={
                            'movie': movie,
                            'base_price': Decimal('250.00'),
                            'available_seats': screen.total_seats,
                            'status': 'OPEN'
                        }
                    )

                    shows.append(show)

        # 6. Users & Sample Bookings
        demo_user, _ = User.objects.get_or_create(
            email='customer@cinepass.com',
            defaults={
                'username': 'customer_demo',
                'first_name': 'John',
                'last_name': 'Doe',
                'role': 'CUSTOMER'
            }
        )
        demo_user.set_password('Password123')
        demo_user.save()

        admin_user, _ = User.objects.get_or_create(
            email='admin@cinepass.com',
            defaults={
                'username': 'admin_demo',
                'first_name': 'CinePass',
                'last_name': 'Admin',
                'role': 'SITE_ADMIN',
                'is_staff': True,
                'is_superuser': True
            }
        )
        admin_user.set_password('AdminPassword123')
        admin_user.save()

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded demo database with {len(created_movies)} movies, {len(theaters)} theaters, {len(shows)} shows, and test users."))
