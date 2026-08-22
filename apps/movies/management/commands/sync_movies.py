import datetime
import logging
import requests
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.utils.text import slugify

from movies.models import Genre, Language, Movie, Cast
from movies.tmdb_service import tmdb_request, fetch_and_sync_movie_credits
from movies.utils.images import normalize_image_url
from movies.utils.tmdb import get_movie_trailer_url, search_tmdb_movie_id
from theaters.models import City, Theater, Screen, Seat
from shows.models import Show

logger = logging.getLogger(__name__)

# Indian regional language mappings
INDIAN_LANG_MAP = {
    'hi': 'Hindi',
    'te': 'Telugu',
    'ta': 'Tamil',
    'ml': 'Malayalam',
    'kn': 'Kannada',
    'mr': 'Marathi',
    'pa': 'Punjabi',
    'bn': 'Bengali',
    'gu': 'Gujarati',
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'ja': 'Japanese',
    'ko': 'Korean',
}

INDIAN_CITIES_AND_THEATERS = [
    {
        'city': 'Mumbai', 'state': 'Maharashtra',
        'theaters': [
            {'name': 'PVR ICON Infinity Mall', 'address': 'Link Road, Andheri West'},
            {'name': 'INOX Megaplex Inorbit Mall', 'address': 'Malad West'},
        ]
    },
    {
        'city': 'Delhi NCR', 'state': 'Delhi',
        'theaters': [
            {'name': 'PVR Director\'s Cut Ambience Mall', 'address': 'Vasant Kunj, New Delhi'},
            {'name': 'Cinepolis DLF Avenue', 'address': 'Saket, New Delhi'},
        ]
    },
    {
        'city': 'Bengaluru', 'state': 'Karnataka',
        'theaters': [
            {'name': 'PVR IMAX Vega City Mall', 'address': 'Bannerghatta Road'},
            {'name': 'INOX Nexus Forum Mall', 'address': 'Koramangala'},
        ]
    },
    {
        'city': 'Hyderabad', 'state': 'Telangana',
        'theaters': [
            {'name': 'Prasads Multiplex Large Screen', 'address': 'NTR Gardens, Necklace Road'},
            {'name': 'AMB Cinemas Gachibowli', 'address': 'Sarath City Capital Mall, Gachibowli'},
        ]
    },
    {
        'city': 'Chennai', 'state': 'Tamil Nadu',
        'theaters': [
            {'name': 'SPI Sathyam Cinemas', 'address': 'Royapettah, Chennai'},
            {'name': 'PVR VR Mall', 'address': 'Jawaharlal Nehru Road, Anna Nagar'},
        ]
    },
]


class Command(BaseCommand):
    help = "Synchronizes latest real-time movie releases, posters, backdrops, trailers, and showtimes from TMDb API."

    def add_arguments(self, parser):
        parser.add_argument(
            '--pages',
            type=int,
            default=2,
            help='Number of pages to synchronize per category (default: 2).'
        )
        parser.add_argument(
            '--repair-only',
            action='store_true',
            help='Only repair existing movie records without fetching new catalog pages.'
        )

    def success(self, msg: str) -> str:
        style_fn = getattr(self.style, 'SUCCESS', str)
        return str(style_fn(msg))

    def handle(self, *args, **options):
        pages = options.get('pages', 2)
        repair_only = options.get('repair_only', False)

        self.stdout.write(self.success(f"Starting CinePass TMDb Movie Synchronization (pages={pages})..."))

        # 1. Sync TMDb Genres Taxonomy
        self.sync_genres()

        total_imported = 0

        if not repair_only:
            # 2. Sync Real-Time TMDb Theatrical Categories
            categories = [
                ('now_playing', '/movie/now_playing'),
                ('popular', '/movie/popular'),
                ('top_rated', '/movie/top_rated'),
                ('upcoming', '/movie/upcoming'),
            ]

            for category_name, endpoint in categories:
                # Primary fetch with region='IN' for localized theatrical releases
                for page in range(1, pages + 1):
                    imported = self.import_category_page(category_name, endpoint, page, region='IN')
                    total_imported += imported

                # Global fallback fetch for blockbuster international releases
                for page in range(1, pages + 1):
                    imported = self.import_category_page(category_name, endpoint, page, region=None)
                    total_imported += imported

            # 3. Discover latest Indian regional releases (Hindi, Telugu, Tamil, Malayalam, Kannada)
            regional_count = self.import_indian_regional_movies(pages=pages)
            total_imported += regional_count

        # 4. Repair any existing movies with missing artwork or details
        repaired_count = self.repair_existing_movies()

        # 5. Generate / Update Indian city theaters, screens, seats, and active showtimes
        shows_count = self.generate_theater_shows()

        self.stdout.write(self.success(
            f"Synchronization Complete: {total_imported} movies synced, {repaired_count} movies repaired, {shows_count} active shows scheduled."
        ))

    def sync_genres(self):
        """Synchronizes official TMDb genre mapping."""
        data = tmdb_request('/genre/movie/list')
        if data and 'genres' in data:
            for g in data['genres']:
                gname = g.get('name')
                if gname:
                    Genre.objects.get_or_create(
                        name=gname,
                        defaults={'slug': slugify(gname)}
                    )

    def import_category_page(self, category_name, endpoint, page, region=None):
        params = {'page': page}
        if region:
            params['region'] = region
        data = tmdb_request(endpoint, params)
        if not data or 'results' not in data:
            return 0
        return self.save_movie_items(data['results'], category_name)

    def import_indian_regional_movies(self, pages=1):
        count = 0
        today = timezone.now().date()
        ninety_days_ago = today - datetime.timedelta(days=90)
        thirty_days_ahead = today + datetime.timedelta(days=30)

        for page in range(1, pages + 1):
            params = {
                'page': page,
                'region': 'IN',
                'with_origin_country': 'IN',
                'primary_release_date.gte': ninety_days_ago.isoformat(),
                'primary_release_date.lte': thirty_days_ahead.isoformat(),
                'sort_by': 'popularity.desc'
            }
            data = tmdb_request('/discover/movie', params)
            if data and 'results' in data:
                count += self.save_movie_items(data['results'], 'now_playing')
        return count

    def save_movie_items(self, results, category_name):
        count = 0
        for item in results:
            tmdb_id = item.get('id')
            title = item.get('title') or item.get('original_title')
            if not tmdb_id or not title:
                continue

            poster_path = item.get('poster_path')
            # Only import movies with valid poster artwork
            if not poster_path:
                continue

            backdrop_path = item.get('backdrop_path')
            poster_url = normalize_image_url(poster_path, size='w500', is_backdrop=False)
            backdrop_url = normalize_image_url(backdrop_path, size='w1280', is_backdrop=True) if backdrop_path else ''

            description = item.get('overview') or 'No plot overview available.'
            tagline = item.get('tagline', '')

            # Parse release date
            release_date = None
            if item.get('release_date'):
                try:
                    release_date = datetime.datetime.strptime(item['release_date'], '%Y-%m-%d').date()
                except Exception:
                    pass
            if not release_date:
                release_date = timezone.now().date()

            # Language
            lang_code = str(item.get('original_language', 'en')).lower()
            lang_name = INDIAN_LANG_MAP.get(lang_code, lang_code.upper())
            lang_obj, _ = Language.objects.get_or_create(code=lang_code, defaults={'name': lang_name})

            rating = Decimal(str(round(item.get('vote_average', 7.5), 1)))
            popularity = int(round(item.get('popularity', 50.0)))

            # Fetch official YouTube trailer
            trailer_url = get_movie_trailer_url(tmdb_id, original_language=lang_code) or ''

            defaults = {
                'title': title,
                'description': description,
                'poster_url': poster_url,
                'backdrop_url': backdrop_url,
                'category': category_name,
                'language': lang_obj,
                'duration': 145,
                'release_date': release_date,
                'rating': rating,
                'popularity': popularity,
                'is_active': True,
            }
            if tagline:
                defaults['tagline'] = tagline
            if trailer_url:
                defaults['trailer_url'] = trailer_url

            # Idempotent match: check by tmdb_id, or by title if tmdb_id was null
            existing = Movie.objects.filter(tmdb_id=tmdb_id).first() or Movie.objects.filter(title=title).first()
            if existing:
                for k, v in defaults.items():
                    setattr(existing, k, v)
                existing.tmdb_id = tmdb_id
                existing.save()
                movie_obj = existing
                created = False
            else:
                movie_obj = Movie.objects.create(tmdb_id=tmdb_id, **defaults)
                created = True

            # Assign genres
            genre_ids = item.get('genre_ids', [])
            if genre_ids:
                genre_objs = Genre.objects.filter(id__in=genre_ids)
                if genre_objs.exists():
                    movie_obj.genres.set(genre_objs)

            # Sync cast & director credits
            try:
                fetch_and_sync_movie_credits(movie_obj, limit=6)
            except Exception:
                pass

            count += 1
            action_str = "Created" if created else "Updated"
            trailer_status = " [+trailer]" if trailer_url else ""
            safe_title = title.encode('ascii', 'replace').decode('ascii')
            logger.info(f"{action_str} [{category_name}] {safe_title} ({lang_name} - TMDb #{tmdb_id}){trailer_status}")

        return count

    def repair_existing_movies(self):
        """Audits and repairs existing movie records with missing artwork or metadata."""
        movies_to_repair = Movie.objects.filter(
            Q(poster_url__isnull=True) | Q(poster_url='') |
            Q(backdrop_url__isnull=True) | Q(backdrop_url='') |
            Q(trailer_url__isnull=True) | Q(trailer_url='') |
            Q(language__isnull=True)
        )

        default_lang = Language.objects.filter(code='en').first() or Language.objects.first()
        if not default_lang:
            default_lang = Language.objects.create(name='English', code='en')

        repaired = 0
        for movie in movies_to_repair:
            if not movie.language:
                movie.language = default_lang
                movie.save(update_fields=['language'])

            tmdb_id = movie.tmdb_id or search_tmdb_movie_id(movie.title, movie.release_date.year if movie.release_date else None)
            if tmdb_id:
                data = tmdb_request(f'/movie/{tmdb_id}')
                if data:
                    movie.tmdb_id = tmdb_id
                    poster_path = data.get('poster_path')
                    backdrop_path = data.get('backdrop_path')
                    if poster_path and not movie.poster_url:
                        movie.poster_url = normalize_image_url(poster_path, size='w500', is_backdrop=False)
                    if backdrop_path and not movie.backdrop_url:
                        movie.backdrop_url = normalize_image_url(backdrop_path, size='w1280', is_backdrop=True)
                    if data.get('tagline') and not movie.tagline:
                        movie.tagline = data.get('tagline')
                    if data.get('runtime') and data.get('runtime') > 0:
                        movie.duration = data.get('runtime')

                    # Trailer check
                    if not movie.trailer_url:
                        lang_code = movie.language.code if movie.language else 'en'
                        trailer_url = get_movie_trailer_url(tmdb_id, original_language=lang_code)
                        if trailer_url:
                            movie.trailer_url = trailer_url

                    movie.save()
                    repaired += 1

        return repaired

    def generate_theater_shows(self):
        """Generates active future shows across all cities & screens for current now_playing movies."""
        now = timezone.now().replace(minute=0, second=0, microsecond=0)
        today = now.date()
        ninety_days_ago = today - datetime.timedelta(days=90)

        all_screens = []
        for cdata in INDIAN_CITIES_AND_THEATERS:
            cname = cdata['city']
            state = cdata['state']
            c_slug = slugify(cname)
            city_obj = City.objects.filter(name=cname).first() or City.objects.filter(slug=c_slug).first()
            if not city_obj:
                city_obj = City.objects.create(name=cname, state=state, slug=c_slug)
            else:
                city_obj.state = state
                city_obj.save()

            for tinfo in cdata['theaters']:
                tname = tinfo['name']
                taddr = tinfo['address']
                t_slug = slugify(f"{tname}-{cname}")
                theater_obj = Theater.objects.filter(name=tname, city=city_obj).first() or Theater.objects.filter(slug=t_slug).first()
                if not theater_obj:
                    theater_obj = Theater.objects.create(
                        name=tname,
                        city=city_obj,
                        address=taddr,
                        slug=t_slug
                    )

                for s_num in range(1, 4):
                    sname = f"Audi {s_num}" if s_num > 1 else "IMAX Laser Screen 1"
                    screen_obj = Screen.objects.filter(theater=theater_obj, name=sname).first()
                    if not screen_obj:
                        screen_obj = Screen.objects.create(
                            theater=theater_obj,
                            name=sname,
                            total_seats=74
                        )
                    all_screens.append(screen_obj)

                    # Ensure seat matrix (74 seats)
                    if screen_obj.seats.count() < 74:
                        seats = []
                        for row in ['A', 'B', 'C', 'D']:
                            for num in range(1, 11):
                                seats.append(Seat(screen=screen_obj, row=row, number=num, seat_type='REGULAR'))
                        for row in ['E', 'F']:
                            for num in range(1, 13):
                                seats.append(Seat(screen=screen_obj, row=row, number=num, seat_type='PREMIUM'))
                        for num in range(1, 11):
                            seats.append(Seat(screen=screen_obj, row='G', number=num, seat_type='RECLINER'))
                        try:
                            Seat.objects.bulk_create(seats, ignore_conflicts=True)
                        except Exception:
                            pass

        if not all_screens:
            return 0

        # Schedule shows for now_playing or recent active movies
        current_movies = list(Movie.objects.filter(
            is_active=True
        ).filter(
            Q(category='now_playing') | Q(release_date__gte=ninety_days_ago)
        ).exclude(poster_url__isnull=True).exclude(poster_url=''))

        if not current_movies:
            current_movies = list(Movie.objects.filter(is_active=True).exclude(poster_url__isnull=True).exclude(poster_url='')[:15])

        shows_created = 0
        prices = [Decimal('220.00'), Decimal('250.00'), Decimal('300.00'), Decimal('350.00')]

        for m_idx, movie in enumerate(current_movies):
            for scr_offset in range(3):
                screen = all_screens[(m_idx * 3 + scr_offset) % len(all_screens)]
                for h_offset in [2, 5, 8, 26, 30, 50, 54]:
                    stime = now + datetime.timedelta(hours=h_offset + (m_idx % 2))
                    etime = stime + datetime.timedelta(minutes=movie.duration + 20)
                    price = prices[(m_idx + scr_offset) % len(prices)]
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
                        shows_created += 1

        return shows_created
