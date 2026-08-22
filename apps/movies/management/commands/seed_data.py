import random
import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from movies.models import Genre, Language, Movie
from theaters.models import City, Theater, Screen, Seat
from shows.models import Show

User = get_user_model()


class Command(BaseCommand):
    help = "Seed database with rich production-ready sample genres, languages, cities, theaters, screens, seats, movies, and active shows."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting CinePass production-ready database seeding..."))

        # 1. Create Superuser & Demo User
        try:
            admin_user = User.objects.filter(email='admin@cinepass.com').first()
            if not admin_user:
                admin_user = User.objects.filter(username='admin').first()
            if not admin_user:
                admin_user = User.objects.create(
                    username='admin',
                    email='admin@cinepass.com',
                    first_name='Admin',
                    last_name='System',
                    role='SITE_ADMIN',
                    is_staff=True,
                    is_superuser=True,
                )
                admin_user.set_password('Admin@123')
                admin_user.save()
                self.stdout.write(self.style.SUCCESS("Created Superuser: admin@cinepass.com / Admin@123"))
            else:
                admin_user.is_staff = True
                admin_user.is_superuser = True
                admin_user.role = 'SITE_ADMIN'
                admin_user.set_password('Admin@123')
                admin_user.save()
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Superuser creation notice: {e}"))

        try:
            demo_user = User.objects.filter(email='user@cinepass.com').first()
            if not demo_user:
                demo_user = User.objects.filter(username='demouser').first()
            if not demo_user:
                demo_user = User.objects.create(
                    username='demouser',
                    email='user@cinepass.com',
                    first_name='Alex',
                    last_name='Morgan',
                    role='CUSTOMER',
                    is_staff=False,
                )
                demo_user.set_password('User@123')
                demo_user.save()
                self.stdout.write(self.style.SUCCESS("Created Demo User: user@cinepass.com / User@123"))
            else:
                demo_user.set_password('User@123')
                demo_user.save()
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Demo user creation notice: {e}"))

        # 2. Seed Languages
        langs_data = [
            ('English', 'en'),
            ('Hindi', 'hi'),
            ('Telugu', 'te'),
            ('Tamil', 'ta'),
            ('Malayalam', 'ml'),
            ('Spanish', 'es'),
            ('French', 'fr'),
        ]
        lang_objs = {}
        for name, code in langs_data:
            obj, _ = Language.objects.get_or_create(code=code, defaults={'name': name})
            lang_objs[code] = obj

        # 3. Seed Genres
        genres_list = [
            'Action', 'Adventure', 'Sci-Fi', 'Drama', 'Thriller',
            'Comedy', 'Romance', 'Animation', 'Horror', 'Crime', 'Fantasy'
        ]
        genre_objs = {}
        for gname in genres_list:
            obj, _ = Genre.objects.get_or_create(name=gname)
            genre_objs[gname] = obj

        # 4. Seed Cities, Theaters, Screens & Full Seat Layouts
        cities_data = [
            ('Mumbai', 'Maharashtra', [
                ('PVR INOX Palladium', 'Phoenix Palladium, Lower Parel, Mumbai'),
                ('Cinepolis Fun Republic', 'Link Road, Andheri West, Mumbai'),
            ]),
            ('Hyderabad', 'Telangana', [
                ('AMB Cinemas', 'Gachibowli, Hyderabad'),
                ('Prasads IMAX', 'NTR Gardens, Necklace Road, Hyderabad'),
            ]),
            ('Bengaluru', 'Karnataka', [
                ('Cinepolis Royal Meenakshi', 'Bannerghatta Main Road, Bengaluru'),
                ('PVR Director Cut', 'Forum Mall, Koramangala, Bengaluru'),
            ]),
            ('Chennai', 'Tamil Nadu', [
                ('SPI Cinemas Luxe', 'Express Avenue Mall, Royapettah, Chennai'),
                ('PVR Heritage RSL', 'East Coast Road, Chennai'),
            ]),
            ('Delhi-NCR', 'Delhi', [
                ('PVR Anupam', 'Community Centre, Saket, New Delhi'),
                ('Miraj Cinemas', 'V3S Mall, Laxmi Nagar, New Delhi'),
            ]),
        ]

        all_screens = []
        screen_types = ['IMAX_3D', '4DX', 'DOLBY_ATMOS', '2D']
        total_seats_created = 0

        for cname, state, th_list in cities_data:
            city_obj, _ = City.objects.get_or_create(name=cname, defaults={'state': state})
            for tname, address in th_list:
                th_obj, _ = Theater.objects.get_or_create(
                    name=tname,
                    city=city_obj,
                    defaults={'address': address, 'is_active': True}
                )
                for s_num in range(1, 4):
                    stype = screen_types[(s_num - 1) % len(screen_types)]
                    screen_obj, _ = Screen.objects.get_or_create(
                        theater=th_obj,
                        name=f'Audi {s_num}',
                        defaults={'screen_type': stype, 'total_seats': 80}
                    )
                    all_screens.append(screen_obj)

                    # Build realistic seat grid: Rows A-H (10 seats each)
                    seats_to_create = []
                    for row_idx, row_letter in enumerate(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']):
                        if row_idx < 3:
                            stier = 'REGULAR'
                        elif row_idx < 6:
                            stier = 'PREMIUM'
                        else:
                            stier = 'RECLINER'

                        for seat_num in range(1, 11):
                            if not Seat.objects.filter(screen=screen_obj, row=row_letter, number=seat_num).exists():
                                seats_to_create.append(Seat(
                                    screen=screen_obj,
                                    row=row_letter,
                                    number=seat_num,
                                    seat_type=stier,
                                    is_active=True
                                ))
                    if seats_to_create:
                        Seat.objects.bulk_create(seats_to_create)
                        total_seats_created += len(seats_to_create)

        # 5. Rich Blockbuster Movies Catalog (Verified TMDb Artwork & Trailers)
        today = timezone.now().date()
        movies_data = [
            {
                'tmdb_id': 1022789,
                'title': 'Kalki 2898 AD',
                'description': 'A modern avatar of Vishnu descends to Earth in 2898 AD to protect humanity against evil supreme forces in a post-apocalyptic world ruled by the Complex.',
                'tagline': 'The future has begun.',
                'language': lang_objs['te'],
                'genres': [genre_objs['Action'], genre_objs['Sci-Fi'], genre_objs['Fantasy']],
                'duration': 180,
                'release_date': datetime.date(2024, 6, 27),
                'rating': Decimal('8.2'),
                'popularity': 95,
                'category': 'now_playing',
                'poster_url': 'https://image.tmdb.org/t/p/w500/61c8vAUp1YtT2P2q44S0Yl90JjL.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/8pjWz2lt29KyVGoVRdUm656WPGf.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=kQDd1AhGIHk',
                'director': 'Nag Ashwin',
            },
            {
                'tmdb_id': 693134,
                'title': 'Dune: Part Two',
                'description': 'Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.',
                'tagline': 'Long live the fighters.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Action'], genre_objs['Adventure'], genre_objs['Sci-Fi']],
                'duration': 166,
                'release_date': datetime.date(2024, 3, 1),
                'rating': Decimal('8.6'),
                'popularity': 98,
                'category': 'popular',
                'poster_url': 'https://image.tmdb.org/t/p/w500/1pdfLPoL6VFi8283vFhMBmWRjJw.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/xOMo8BRK7PfcJv9JCnx7s520bEx.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=Way9Dexny3w',
                'director': 'Denis Villeneuve',
            },
            {
                'tmdb_id': 872585,
                'title': 'Oppenheimer',
                'description': 'The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb during World War II.',
                'tagline': 'The world forever changes.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Drama'], genre_objs['Thriller']],
                'duration': 180,
                'release_date': datetime.date(2023, 7, 21),
                'rating': Decimal('8.9'),
                'popularity': 96,
                'category': 'top_rated',
                'poster_url': 'https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGvC271sC21.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/fm6KqXpk3M2HVveHwCrBSSBaO0V.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=uYPbbksJxIg',
                'director': 'Christopher Nolan',
            },
            {
                'tmdb_id': 533535,
                'title': 'Deadpool & Wolverine',
                'description': 'A listless Wade Wilson toils away in civilian life with his days as the morally flexible mercenary Deadpool behind him, until the TVA pulls him into a new mission.',
                'tagline': 'Come together.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Action'], genre_objs['Comedy'], genre_objs['Sci-Fi']],
                'duration': 128,
                'release_date': datetime.date(2024, 7, 26),
                'rating': Decimal('8.3'),
                'popularity': 97,
                'category': 'now_playing',
                'poster_url': 'https://image.tmdb.org/t/p/w500/8cdWjvZQUExUUTzyp4t6EDMubfO.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/yDHYTfaA95BTy9vsOHENN3mK3aP.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=73_1biulkYk',
                'director': 'Shawn Levy',
            },
            {
                'tmdb_id': 157336,
                'title': 'Interstellar',
                'description': 'The adventures of a group of explorers who make use of a newly discovered wormhole to surpass the limitations on human space travel.',
                'tagline': 'Mankind was born on Earth. It was never meant to die here.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Adventure'], genre_objs['Drama'], genre_objs['Sci-Fi']],
                'duration': 169,
                'release_date': datetime.date(2014, 11, 7),
                'rating': Decimal('8.9'),
                'popularity': 97,
                'category': 'top_rated',
                'poster_url': 'https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/xJHokMbljvjADYdit5fK5VQsXEG.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=zSWdZVtXT7E',
                'director': 'Christopher Nolan',
            },
            {
                'tmdb_id': 569094,
                'title': 'Spider-Man: Across the Spider-Verse',
                'description': 'Miles Morales catapults across the Multiverse, where he encounters a team of Spider-People charged with protecting its very existence.',
                'tagline': 'It\'s how you wear the mask that matters.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Animation'], genre_objs['Action'], genre_objs['Adventure']],
                'duration': 140,
                'release_date': datetime.date(2023, 6, 2),
                'rating': Decimal('8.7'),
                'popularity': 95,
                'category': 'top_rated',
                'poster_url': 'https://image.tmdb.org/t/p/w500/8Vt6mWEReuy4Of61Lnj5Xj704m8.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/4HodYYKEIsGOdinkGi2Ucz6X9i0.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=cqGjhVJWtEg',
                'director': 'Joaquim Dos Santos',
            },
            {
                'tmdb_id': 155,
                'title': 'The Dark Knight',
                'description': 'Batman raises the stakes in his war on crime with the help of Lt. Jim Gordon and District Attorney Harvey Dent, but finds himself tested by a criminal mastermind known as The Joker.',
                'tagline': 'Why so serious?',
                'language': lang_objs['en'],
                'genres': [genre_objs['Action'], genre_objs['Crime'], genre_objs['Drama']],
                'duration': 152,
                'release_date': datetime.date(2008, 7, 18),
                'rating': Decimal('9.0'),
                'popularity': 99,
                'category': 'top_rated',
                'poster_url': 'https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/nMKdUUepR0i5zn0y1T4CsSB5chy.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=EXeTwQWrcwY',
                'director': 'Christopher Nolan',
            },
            {
                'tmdb_id': 27205,
                'title': 'Inception',
                'description': 'Cobb, a skilled thief who commits corporate espionage by infiltrating the subconscious of his targets, is offered a chance to regain his old life in exchange for an almost impossible task: "inception".',
                'tagline': 'Your mind is the scene of the crime.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Action'], genre_objs['Sci-Fi'], genre_objs['Adventure']],
                'duration': 148,
                'release_date': datetime.date(2010, 7, 16),
                'rating': Decimal('8.8'),
                'popularity': 96,
                'category': 'top_rated',
                'poster_url': 'https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/s3TBrRGB1iav7gFOCNx3H31MoES.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=YoHD9XEInc0',
                'director': 'Christopher Nolan',
            },
            {
                'tmdb_id': 76600,
                'title': 'Avatar: The Way of Water',
                'description': 'Set more than a decade after the events of the first film, learn the story of the Sully family, the trouble that follows them, and the battles they fight to stay alive.',
                'tagline': 'Return to Pandora.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Action'], genre_objs['Adventure'], genre_objs['Sci-Fi']],
                'duration': 192,
                'release_date': datetime.date(2022, 12, 16),
                'rating': Decimal('8.5'),
                'popularity': 93,
                'category': 'popular',
                'poster_url': 'https://image.tmdb.org/t/p/w500/t6HIqrRAclMCA60NsSmeqe9RmNV.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/s16H6tpK2utvwDtzZIMQn06qjwN.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=d9MyW72ELq0',
                'director': 'James Cameron',
            },
            {
                'tmdb_id': 579974,
                'title': 'RRR',
                'description': 'A fictional history of two legendary revolutionaries\' journey away from home before they began fighting for their country in the 1920s.',
                'tagline': 'Rise, Roar, Revolt.',
                'language': lang_objs['te'],
                'genres': [genre_objs['Action'], genre_objs['Drama']],
                'duration': 187,
                'release_date': datetime.date(2022, 3, 25),
                'rating': Decimal('8.4'),
                'popularity': 94,
                'category': 'top_rated',
                'poster_url': 'https://image.tmdb.org/t/p/w500/nEufeZlyAOLqO2brrs0ye21lgdp.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/wPU78OPN4BYEgWYdXyg0phMee61.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=GY4BgdUSpbE',
                'director': 'S.S. Rajamouli',
            },
            {
                'tmdb_id': 299534,
                'title': 'Avengers: Endgame',
                'description': 'After the devastating events of Infinity War, the universe is in ruins. With the help of remaining allies, the Avengers assemble once more to reverse Thanos\' actions.',
                'tagline': 'Part of the journey is the end.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Action'], genre_objs['Adventure'], genre_objs['Sci-Fi']],
                'duration': 181,
                'release_date': datetime.date(2019, 4, 26),
                'rating': Decimal('8.8'),
                'popularity': 98,
                'category': 'top_rated',
                'poster_url': 'https://image.tmdb.org/t/p/w500/or06FN3Dka5tukK1e9sl16pB3iy.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/7RyHsO4yDXtBv1zUU3mTpHeQ0d5.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=TcMBFSGVi1c',
                'director': 'Anthony Russo, Joe Russo',
            },
            {
                'tmdb_id': 945961,
                'title': 'Alien: Romulus',
                'description': 'While scavenging the deep ends of a derelict space station, a group of young space colonizers come face to face with the most terrifying life form in the universe.',
                'tagline': 'In space no one can hear you.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Horror'], genre_objs['Sci-Fi'], genre_objs['Thriller']],
                'duration': 119,
                'release_date': datetime.date(2024, 8, 16),
                'rating': Decimal('8.1'),
                'popularity': 94,
                'category': 'now_playing',
                'poster_url': 'https://image.tmdb.org/t/p/w500/b33nnKl1GSFbao8l3fZkyR4duF8.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/9SSEUrSqhljBMzRe4aBTh17rUaC.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=x0XDEhP4MQs',
                'director': 'Fede Alvarez',
            },
            {
                'tmdb_id': 1184918,
                'title': 'The Wild Robot',
                'description': 'After a shipwreck, an intelligent robot named Roz is stranded on an uninhabited island and must learn to adapt to the harsh surroundings.',
                'tagline': 'Discover your true nature.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Animation'], genre_objs['Sci-Fi'], genre_objs['Adventure']],
                'duration': 102,
                'release_date': datetime.date(2024, 9, 27),
                'rating': Decimal('8.5'),
                'popularity': 92,
                'category': 'upcoming',
                'poster_url': 'https://image.tmdb.org/t/p/w500/wTnV3PCVW5O92JMrFvvrRcV39RU.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/mQZJoIhTEkNhCYJsWEzhgIuWWuW.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=67vbA5ZJdKQ',
                'director': 'Chris Sanders',
            },
            {
                'tmdb_id': 917496,
                'title': 'Beetlejuice Beetlejuice',
                'description': 'After a family tragedy, three generations of the Deetz family return home to Winter River. Still haunted by Beetlejuice, Lydia\'s life is turned upside down.',
                'tagline': 'The juice is loose.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Comedy'], genre_objs['Fantasy'], genre_objs['Horror']],
                'duration': 104,
                'release_date': datetime.date(2024, 9, 6),
                'rating': Decimal('7.8'),
                'popularity': 90,
                'category': 'now_playing',
                'poster_url': 'https://image.tmdb.org/t/p/w500/kKgQzkUCUm04cuE9T52i5975YpU.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/xi1VbtRDDsfTOfdqo7vBTIGNOFs.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=As-vKW4ZpbY',
                'director': 'Tim Burton',
            },
            {
                'tmdb_id': 933260,
                'title': 'The Substance',
                'description': 'A fading celebrity takes a black-market drug: a cell-replicating substance that temporarily creates a younger, better version of herself.',
                'tagline': 'If you respect the balance, what could go wrong?',
                'language': lang_objs['en'],
                'genres': [genre_objs['Drama'], genre_objs['Horror'], genre_objs['Sci-Fi']],
                'duration': 141,
                'release_date': datetime.date(2024, 9, 20),
                'rating': Decimal('8.0'),
                'popularity': 89,
                'category': 'now_playing',
                'poster_url': 'https://image.tmdb.org/t/p/w500/lqoMzCcZYEFK72906VZwVeQIAlr.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/7h6TqPB3ES5RiCekCc9QKV5neFE.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=LNlrGhPdnC8',
                'director': 'Coralie Fargeat',
            },
            {
                'tmdb_id': 1064028,
                'title': 'Gladiator II',
                'description': 'Years after witnessing the death of Maximus at the hands of his uncle, Lucius must enter the Colosseum after the powerful emperors of Rome conquer his home.',
                'tagline': 'Prepare to be entertained.',
                'language': lang_objs['en'],
                'genres': [genre_objs['Action'], genre_objs['Adventure'], genre_objs['Drama']],
                'duration': 148,
                'release_date': datetime.date(2024, 11, 22),
                'rating': Decimal('8.6'),
                'popularity': 98,
                'category': 'upcoming',
                'poster_url': 'https://image.tmdb.org/t/p/w500/2cxhvwyEwRlysAmRH4iodkvo0z5.jpg',
                'backdrop_url': 'https://image.tmdb.org/t/p/w1280/euYIwmwkmz95mnXvufEmbL69ovr.jpg',
                'trailer_url': 'https://www.youtube.com/watch?v=4rgYUipGJNo',
                'director': 'Ridley Scott',
            },
        ]

        created_movies = []
        for mdata in movies_data:
            try:
                genres = mdata.pop('genres')
                tmdb_id = mdata.pop('tmdb_id', None)
                movie_obj = Movie.objects.filter(title=mdata['title']).first()
                if not movie_obj and tmdb_id:
                    movie_obj = Movie.objects.filter(tmdb_id=tmdb_id).first()
                
                if movie_obj:
                    for k, v in mdata.items():
                        setattr(movie_obj, k, v)
                    if tmdb_id:
                        movie_obj.tmdb_id = tmdb_id
                    movie_obj.is_active = True
                    movie_obj.save()
                else:
                    movie_obj = Movie.objects.create(
                        tmdb_id=tmdb_id,
                        is_active=True,
                        **mdata
                    )
                movie_obj.genres.set(genres)
                created_movies.append(movie_obj)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Movie seed notice for {mdata.get('title')}: {e}"))

        # 6. Seed Active Shows across screens with unique showtimes
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        shows_count = 0
        prices = [Decimal('220.00'), Decimal('250.00'), Decimal('300.00'), Decimal('350.00')]

        for m_idx, movie in enumerate(created_movies):
            for scr_offset in range(3):
                if not all_screens:
                    break
                screen = all_screens[(m_idx * 3 + scr_offset) % len(all_screens)]
                for h_offset in [2, 5, 8, 26, 30, 50, 54]:
                    stime = now + datetime.timedelta(hours=h_offset + (m_idx % 2))
                    etime = stime + datetime.timedelta(minutes=movie.duration + 20)
                    price = prices[(m_idx + scr_offset) % len(prices)]
                    try:
                        show_obj, created = Show.objects.get_or_create(
                            screen=screen,
                            start_time=stime,
                            defaults={
                                'movie': movie,
                                'end_time': etime,
                                'base_price': price,
                                'available_seats': screen.total_seats,
                                'status': 'OPEN'
                            }
                        )
                        if created:
                            shows_count += 1
                    except Exception:
                        pass

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded CinePass database! Created {len(created_movies)} Movies, {len(all_screens)} Screens with {total_seats_created} Seats, and {shows_count} Active Shows."
        ))
