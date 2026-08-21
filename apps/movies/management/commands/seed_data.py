import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from movies.models import Genre, Language, Movie
from theaters.models import City, Theater, Screen
from shows.models import Show

User = get_user_model()

class Command(BaseCommand):
    help = "Seed database with initial sample genres, languages, cities, theaters, screens, movies, and shows."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting database seeding process..."))

        # 1. Create Superuser & Demo User
        admin_user, created = User.objects.get_or_create(
            username='admin',
            email='admin@cinepass.com',
            defaults={
                'first_name': 'Admin',
                'last_name': 'System',
                'role': 'SITE_ADMIN',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('Admin@123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created Superuser: admin@cinepass.com / Admin@123"))

        demo_user, created = User.objects.get_or_create(
            username='demouser',
            email='user@cinepass.com',
            defaults={
                'first_name': 'Alex',
                'last_name': 'Morgan',
                'role': 'CUSTOMER',
                'is_staff': False,
            }
        )
        if created:
            demo_user.set_password('User@123')
            demo_user.save()
            self.stdout.write(self.style.SUCCESS("Created Demo User: user@cinepass.com / User@123"))

        # 2. Seed Languages
        langs = [
            ('English', 'en'),
            ('Hindi', 'hi'),
            ('Telugu', 'te'),
            ('Spanish', 'es'),
            ('French', 'fr'),
        ]
        lang_objs = {}
        for name, code in langs:
            obj, _ = Language.objects.get_or_create(name=name, defaults={'code': code})
            lang_objs[name] = obj

        # 3. Seed Genres
        genres_list = ['Action', 'Adventure', 'Sci-Fi', 'Drama', 'Thriller', 'Comedy', 'Romance', 'Animation', 'Horror']
        genre_objs = {}
        for gname in genres_list:
            obj, _ = Genre.objects.get_or_create(name=gname)
            genre_objs[gname] = obj

        # 4. Seed Cities, Theaters & Screens
        cities_data = [
            ('New York', 'NY', [
                ('AMC Empire 25', '234 W 42nd St, New York, NY 10036'),
                ('Regal Union Square', '850 Broadway, New York, NY 10003'),
            ]),
            ('Los Angeles', 'CA', [
                ('Regal LA LIVE', '1000 W Olympic Blvd, Los Angeles, CA 90015'),
                ('TCL Chinese Theatre', '6925 Hollywood Blvd, Hollywood, CA 90028'),
            ]),
            ('Hyderabad', 'TS', [
                ('Prasads IMAX', 'NTR Gardens, Lic Division, Hyderabad'),
                ('AMB Cinemas', 'Gachibowli, Hyderabad'),
            ]),
        ]

        screens_pool = []
        for cname, state, th_list in cities_data:
            city_obj, _ = City.objects.get_or_create(name=cname, defaults={'state': state})
            for tname, address in th_list:
                th_obj, _ = Theater.objects.get_or_create(name=tname, city=city_obj, defaults={'address': address})
                for s_num in range(1, 3):
                    screen_obj, _ = Screen.objects.get_or_create(
                        theater=th_obj,
                        name=f'Audi {s_num}',
                        defaults={'screen_type': 'IMAX_3D' if s_num == 1 else '2D', 'total_seats': 100}
                    )
                    screens_pool.append(screen_obj)

        # 5. Seed Movies
        movies_data = [
            {
                'title': 'Dune: Part Two',
                'description': 'Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.',
                'language': lang_objs['English'],
                'genres': [genre_objs['Action'], genre_objs['Adventure'], genre_objs['Sci-Fi']],
                'duration': 166,
                'release_date': datetime.date(2024, 3, 1),
                'rating': 8.8,
                'popularity': 98,
                'trailer_url': 'https://www.youtube.com/watch?v=Way9Dexny3w',
            },
            {
                'title': 'Oppenheimer',
                'description': 'The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb.',
                'language': lang_objs['English'],
                'genres': [genre_objs['Drama'], genre_objs['Thriller']],
                'duration': 180,
                'release_date': datetime.date(2023, 7, 21),
                'rating': 8.9,
                'popularity': 96,
                'trailer_url': 'https://www.youtube.com/watch?v=uYPbbksJxIg',
            },
            {
                'title': 'Kalki 2898 AD',
                'description': 'A modern avatar of Vishnu, a Hindu god, who is believed to have descended to earth to protect the world from evil forces.',
                'language': lang_objs['Telugu'],
                'genres': [genre_objs['Action'], genre_objs['Sci-Fi']],
                'duration': 181,
                'release_date': datetime.date(2024, 6, 27),
                'rating': 8.2,
                'popularity': 90,
                'trailer_url': 'https://www.youtube.com/watch?v=kQDd1AhGIHk',
            },
        ]

        created_movies = []
        for mdata in movies_data:
            genres = mdata.pop('genres')
            movie_obj, m_created = Movie.objects.get_or_create(
                title=mdata['title'],
                defaults=mdata
            )
            if m_created:
                movie_obj.genres.set(genres)
            created_movies.append(movie_obj)

        # 6. Seed Shows across screens with unique showtime offsets
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        shows_count = 0
        for m_idx, movie in enumerate(created_movies):
            screen = screens_pool[m_idx % len(screens_pool)]
            for h_offset in [2, 6, 24, 30]:
                stime = now + datetime.timedelta(hours=h_offset + (m_idx * 3))
                _, created = Show.objects.get_or_create(
                    screen=screen,
                    start_time=stime,
                    defaults={
                        'movie': movie,
                        'base_price': 250.00,
                        'available_seats': 100,
                        'status': 'OPEN'
                    }
                )
                if created:
                    shows_count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded database! Created {len(created_movies)} Movies and {shows_count} Active Shows."))
