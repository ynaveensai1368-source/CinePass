import datetime
import logging
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model

from movies.models import Genre, Language, Movie
from theaters.models import City, Theater, Screen, Seat
from shows.models import Show

logger = logging.getLogger(__name__)
User = get_user_model()


def seed_production_catalog():
    """
    Idempotent, highly resilient catalog population function.
    Safely seeds initial languages, genres, cities, theaters, screens, seats,
    16 blockbuster movies with authentic TMDb artwork, and 210+ active showtimes.
    """
    logger.info("Starting CinePass production catalog seeding...")

    # 1. Superuser and Demo User
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
        else:
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.role = 'SITE_ADMIN'
            admin_user.set_password('Admin@123')
            admin_user.save()
    except Exception as e:
        logger.warning(f"Admin user seeding notice: {e}")

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
        else:
            demo_user.set_password('User@123')
            demo_user.save()
    except Exception as e:
        logger.warning(f"Demo user seeding notice: {e}")

    # 2. Languages
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
        try:
            obj = Language.objects.filter(code=code).first() or Language.objects.filter(name=name).first()
            if not obj:
                obj = Language.objects.create(name=name, code=code)
            lang_objs[code] = obj
        except Exception as e:
            logger.warning(f"Language seeding notice for {code}: {e}")

    default_lang = lang_objs.get('en') or Language.objects.first()
    if not default_lang:
        default_lang = Language.objects.create(name='English', code='en')
        lang_objs['en'] = default_lang

    # 3. Genres
    genres_list = [
        'Action', 'Adventure', 'Sci-Fi', 'Drama', 'Thriller',
        'Comedy', 'Romance', 'Animation', 'Horror', 'Crime', 'Fantasy'
    ]
    genre_objs = {}
    for gname in genres_list:
        try:
            obj = Genre.objects.filter(name=gname).first()
            if not obj:
                from django.utils.text import slugify
                obj = Genre.objects.create(name=gname, slug=slugify(gname))
            genre_objs[gname] = obj
        except Exception as e:
            logger.warning(f"Genre seeding notice for {gname}: {e}")

    # 4. Cities, Theaters, Screens & Full Seat Layouts
    cities_data = [
        ('Mumbai', 'Maharashtra', [
            ('PVR ICON Infinity Mall', 'Link Road, Andheri West', 3),
            ('INOX Megaplex Inorbit Mall', 'Malad West', 3),
        ]),
        ('Delhi NCR', 'Delhi', [
            ('PVR Director\'s Cut Ambience Mall', 'Vasant Kunj, New Delhi', 3),
            ('Cinepolis DLF Avenue', 'Saket, New Delhi', 3),
        ]),
        ('Bengaluru', 'Karnataka', [
            ('PVR IMAX Vega City Mall', 'Bannerghatta Road', 3),
            ('INOX Nexus Forum Mall', 'Koramangala', 3),
        ]),
        ('Hyderabad', 'Telangana', [
            ('Prasads Multiplex Large Screen', 'NTR Gardens, Necklace Road', 3),
            ('AMB Cinemas Gachibowli', 'Sarath City Capital Mall, Gachibowli', 3),
        ]),
        ('Chennai', 'Tamil Nadu', [
            ('SPI Sathyam Cinemas', 'Royapettah, Chennai', 3),
            ('PVR VR Mall', 'Jawaharlal Nehru Road, Anna Nagar', 3),
        ]),
    ]

    all_screens = []
    total_seats_created = 0

    for cname, state, theaters in cities_data:
        try:
            from django.utils.text import slugify
            c_slug = slugify(cname)
            city_obj = City.objects.filter(name=cname).first() or City.objects.filter(slug=c_slug).first()
            if not city_obj:
                city_obj = City.objects.create(name=cname, state=state, slug=c_slug)
            else:
                city_obj.state = state
                city_obj.save()
            for tname, taddr, screen_count in theaters:
                theater_obj = Theater.objects.filter(name=tname, city=city_obj).first()
                if not theater_obj:
                    from django.utils.text import slugify
                    theater_obj = Theater.objects.create(
                        name=tname,
                        city=city_obj,
                        address=taddr,
                        slug=slugify(f"{tname}-{cname}")
                    )
                for s_num in range(1, screen_count + 1):
                    screen_name = f"Audi {s_num}" if s_num > 1 else "IMAX Laser Screen 1"
                    screen_obj = Screen.objects.filter(theater=theater_obj, name=screen_name).first()
                    if not screen_obj:
                        screen_obj = Screen.objects.create(
                            theater=theater_obj,
                            name=screen_name,
                            total_seats=74
                        )
                    all_screens.append(screen_obj)

                    # Create seat matrix if not already present
                    if screen_obj.seats.count() < 74:
                        seats_to_create = []
                        # 4 rows of Regular (A-D, 1-10) = 40 seats
                        for row in ['A', 'B', 'C', 'D']:
                            for num in range(1, 11):
                                seats_to_create.append(
                                    Seat(screen=screen_obj, row=row, number=num, seat_type='REGULAR')
                                )
                        # 2 rows of Premium (E-F, 1-12) = 24 seats
                        for row in ['E', 'F']:
                            for num in range(1, 13):
                                seats_to_create.append(
                                    Seat(screen=screen_obj, row=row, number=num, seat_type='PREMIUM')
                                )
                        # 1 row of Recliner (G, 1-10) = 10 seats
                        for num in range(1, 11):
                            seats_to_create.append(
                                Seat(screen=screen_obj, row='G', number=num, seat_type='RECLINER')
                            )
                        try:
                            Seat.objects.bulk_create(seats_to_create, ignore_conflicts=True)
                            total_seats_created += len(seats_to_create)
                        except Exception as e:
                            logger.warning(f"Seats creation notice: {e}")
        except Exception as e:
            logger.warning(f"City/Theater creation notice for {cname}: {e}")

    # 5. 16 Blockbuster Movies with authentic TMDb Artwork
    movies_data = [
        {
            'tmdb_id': 945961,
            'title': 'Alien: Romulus',
            'description': 'While scavenging the deep ends of a derelict space station, a group of young space colonizers come face to face with the most terrifying life form in the universe.',
            'tagline': 'In space no one can hear you scream.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Sci-Fi', 'Horror', 'Thriller'] if g in genre_objs],
            'duration': 119,
            'release_date': datetime.date(2024, 8, 16),
            'rating': Decimal('8.4'),
            'popularity': 100,
            'category': 'now_playing',
            'poster_url': 'https://image.tmdb.org/t/p/w500/b33nnKl1GSvbao8l3UIDTFx0qL9.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/9SSEUrSqhljBMzRe4aBTh17rUaC.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=x0XDEhP4MQs',
            'director': 'Fede Alvarez',
        },
        {
            'tmdb_id': 693134,
            'title': 'Dune: Part Two',
            'description': 'Follow the mythic journey of Paul Atreides as he unites with Chani and the Fremen while on a path of revenge against the conspirators who destroyed his family.',
            'tagline': 'Long live the fighters.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Sci-Fi', 'Adventure', 'Action'] if g in genre_objs],
            'duration': 166,
            'release_date': datetime.date(2024, 3, 1),
            'rating': Decimal('8.8'),
            'popularity': 99,
            'category': 'now_playing',
            'poster_url': 'https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/xOMo8BRK7PfcJv9JCnx7s520b4q.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=Way9Dexny3w',
            'director': 'Denis Villeneuve',
        },
        {
            'tmdb_id': 872585,
            'title': 'Oppenheimer',
            'description': 'The story of J. Robert Oppenheimer’s role in the development of the atomic bomb during World War II and the subsequent security hearings.',
            'tagline': 'The world forever changes.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Drama', 'Thriller'] if g in genre_objs],
            'duration': 180,
            'release_date': datetime.date(2023, 7, 21),
            'rating': Decimal('8.9'),
            'popularity': 96,
            'category': 'popular',
            'poster_url': 'https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/rLb2cwF3Pazuxaj0sRXQ037tGI1.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=uYPbbksJxIg',
            'director': 'Christopher Nolan',
        },
        {
            'tmdb_id': 792307,
            'title': 'Kalki 2898 AD',
            'description': 'A modern avatar of Vishnu descends to Earth to protect humanity against evil dark forces in a post-apocalyptic dystopian world set in Kasi.',
            'tagline': 'The future begins now.',
            'language': lang_objs.get('te') or lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Action', 'Sci-Fi', 'Fantasy'] if g in genre_objs],
            'duration': 181,
            'release_date': datetime.date(2024, 6, 27),
            'rating': Decimal('8.5'),
            'popularity': 98,
            'category': 'now_playing',
            'poster_url': 'https://image.tmdb.org/t/p/w500/z0J22kC9b90g4R5c9359qY8Q5b8.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/8pjWz2lt29KyVGoVRReUmLgrtOX.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=kQDd1AhGIHk',
            'director': 'Nag Ashwin',
        },
        {
            'tmdb_id': 533535,
            'title': 'Deadpool & Wolverine',
            'description': 'A listless Wade Wilson toils away in civilian life with his days as the morally flexible mercenary Deadpool behind him, until the TVA pulls him into a new mission.',
            'tagline': 'Come together.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Action', 'Comedy', 'Sci-Fi'] if g in genre_objs],
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
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Adventure', 'Drama', 'Sci-Fi'] if g in genre_objs],
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
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Animation', 'Action', 'Adventure'] if g in genre_objs],
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
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Action', 'Crime', 'Drama'] if g in genre_objs],
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
            'description': 'Cobb, a skilled thief who steals corporate secrets through the use of dream-sharing technology, is given the inverse task of planting an idea into the mind of a C.E.O.',
            'tagline': 'Your mind is the scene of the crime.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Action', 'Sci-Fi', 'Adventure'] if g in genre_objs],
            'duration': 148,
            'release_date': datetime.date(2010, 7, 16),
            'rating': Decimal('8.8'),
            'popularity': 96,
            'category': 'top_rated',
            'poster_url': 'https://image.tmdb.org/t/p/w500/oYuLEt3zVCKq57qu2F8dT7NIa6f.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/8ZTVqvKDQ8emSGUEMjsS4yHAwrp.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=YoHD9XEInc0',
            'director': 'Christopher Nolan',
        },
        {
            'tmdb_id': 76600,
            'title': 'Avatar: The Way of Water',
            'description': 'Set more than a decade after the events of the first film, learn the story of the Sully family, the trouble that follows them, the lengths they go to keep each other safe, the battles they fight to stay alive, and the tragedies they endure.',
            'tagline': 'Return to Pandora.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Sci-Fi', 'Action', 'Adventure'] if g in genre_objs],
            'duration': 192,
            'release_date': datetime.date(2022, 12, 16),
            'rating': Decimal('8.5'),
            'popularity': 95,
            'category': 'popular',
            'poster_url': 'https://image.tmdb.org/t/p/w500/t6HIqrRAclMCA60NsSmeqe9RmNV.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/s16H6tpK2utvwDtzZIMQn06qjwn.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=d9MyW72ELq0',
            'director': 'James Cameron',
        },
        {
            'tmdb_id': 579974,
            'title': 'RRR',
            'description': 'A fictional tale about two legendary revolutionaries and their journey away from home before they started fighting for their country in 1920\'s.',
            'tagline': 'Rise, Roar, Revolt.',
            'language': lang_objs.get('te') or lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Action', 'Drama'] if g in genre_objs],
            'duration': 187,
            'release_date': datetime.date(2022, 3, 25),
            'rating': Decimal('8.7'),
            'popularity': 94,
            'category': 'popular',
            'poster_url': 'https://image.tmdb.org/t/p/w500/wE0SilTGheVI8hxVo9iAH3TXGVV.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/m03bO4vdI3noIsRJMR7iM88P4nC.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=GY4BgdUSpbE',
            'director': 'S.S. Rajamouli',
        },
        {
            'tmdb_id': 299534,
            'title': 'Avengers: Endgame',
            'description': 'After the devastating events of Avengers: Infinity War, the universe is in ruins. With the help of remaining allies, the Avengers assemble once more in order to reverse Thanos\' actions and restore balance to the universe.',
            'tagline': 'Part of the journey is the end.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Adventure', 'Sci-Fi', 'Action'] if g in genre_objs],
            'duration': 181,
            'release_date': datetime.date(2019, 4, 26),
            'rating': Decimal('8.9'),
            'popularity': 98,
            'category': 'top_rated',
            'poster_url': 'https://image.tmdb.org/t/p/w500/or06FN3Dka5tukK1e9sl16pB3iy.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/7RyHsO4yDXtBv1zUU3mTpHeQ0d5.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=TcMBFSGVi1c',
            'director': 'Anthony Russo, Joe Russo',
        },
        {
            'tmdb_id': 1184918,
            'title': 'The Wild Robot',
            'description': 'After a shipwreck, an intelligent robot named Roz is stranded on an uninhabited island. To survive the harsh environment, Roz bonds with the island\'s animals and cares for an orphaned baby goose.',
            'tagline': 'Discover your true nature.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Animation', 'Sci-Fi', 'Family'] if g in genre_objs],
            'duration': 102,
            'release_date': datetime.date(2024, 9, 27),
            'rating': Decimal('8.6'),
            'popularity': 96,
            'category': 'now_playing',
            'poster_url': 'https://image.tmdb.org/t/p/w500/wTnV3PCVW5O92JMrFvvrRcV39RU.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/417tYZ4um9yhBR6voYUsJQNcTnK.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=67vbA5ZJdKQ',
            'director': 'Chris Sanders',
        },
        {
            'tmdb_id': 917496,
            'title': 'Beetlejuice Beetlejuice',
            'description': 'After a family tragedy, three generations of the Deetz family return home to Winter River. Still haunted by Beetlejuice, Lydia\'s life is turned upside down when her teenage daughter, Astrid, accidentally opens the portal to the Afterlife.',
            'tagline': 'The juice is loose.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Comedy', 'Fantasy', 'Horror'] if g in genre_objs],
            'duration': 104,
            'release_date': datetime.date(2024, 9, 6),
            'rating': Decimal('8.1'),
            'popularity': 95,
            'category': 'now_playing',
            'poster_url': 'https://image.tmdb.org/t/p/w500/kKgQzkUCUm0meqTnVoqSNmm9i0q.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/xi1VSt3lRTgCu5JeWpqG5ktdEVe.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=As-vKW4ZboY',
            'director': 'Tim Burton',
        },
        {
            'tmdb_id': 933260,
            'title': 'The Substance',
            'description': 'A fading celebrity decides to use a black market drug, a cell-replicating substance that temporarily creates a younger, better version of herself.',
            'tagline': 'If you respect the balance, what could possibly go wrong?',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Horror', 'Drama', 'Sci-Fi'] if g in genre_objs],
            'duration': 141,
            'release_date': datetime.date(2024, 9, 20),
            'rating': Decimal('8.2'),
            'popularity': 93,
            'category': 'now_playing',
            'poster_url': 'https://image.tmdb.org/t/p/w500/lqoMzCcZYEFK72906V3KyFF4xez.jpg',
            'backdrop_url': 'https://image.tmdb.org/t/p/w1280/7h6TqPB3ESmjuVbxmpBOKCD57L3.jpg',
            'trailer_url': 'https://www.youtube.com/watch?v=LNlrGhBpYjc',
            'director': 'Coralie Fargeat',
        },
        {
            'tmdb_id': 558449,
            'title': 'Gladiator II',
            'description': 'Years after witnessing the death of the revered hero Maximus at the hands of his uncle, Lucius must enter the Colosseum after his home is conquered by the tyrannical Emperors who now lead Rome with an iron fist.',
            'tagline': 'What we do in life echoes in eternity.',
            'language': lang_objs.get('en'),
            'genres': [genre_objs[g] for g in ['Action', 'Adventure', 'Drama'] if g in genre_objs],
            'duration': 148,
            'release_date': datetime.date(2024, 11, 15),
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
            genres = mdata.pop('genres', [])
            tmdb_id = mdata.pop('tmdb_id', None)
            if not mdata.get('language'):
                mdata['language'] = default_lang

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
            if genres:
                movie_obj.genres.set(genres)
            created_movies.append(movie_obj)
        except Exception as e:
            logger.warning(f"Movie seed notice for {mdata.get('title')}: {e}")

    # 6. Active Shows across screens with unique showtimes
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

    logger.info(f"CinePass catalog seeded: {len(created_movies)} movies, {len(all_screens)} screens, {shows_count} shows.")
    return len(created_movies)
