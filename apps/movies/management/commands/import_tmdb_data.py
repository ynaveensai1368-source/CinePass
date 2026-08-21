import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from movies.models import Genre, Language, Movie
from movies.tmdb_service import tmdb_request
from theaters.models import City, Theater, Screen
from shows.models import Show

# Language code map for Indian regional languages
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
}

INDIAN_CITIES_AND_THEATERS = [
    {
        'city': 'Mumbai', 'state': 'Maharashtra',
        'theaters': [
            {'name': 'PVR INOX Zenith', 'address': 'Phoenix Palladium, Lower Parel'},
            {'name': 'Cinepolis Fun Republic', 'address': 'Andheri West'},
        ]
    },
    {
        'city': 'Hyderabad', 'state': 'Telangana',
        'theaters': [
            {'name': 'AMB Cinemas', 'address': 'Gachibowli'},
            {'name': 'Prasads Multiplex', 'address': 'NTR Gardens'},
        ]
    },
    {
        'city': 'Bengaluru', 'state': 'Karnataka',
        'theaters': [
            {'name': 'Cinepolis Royal Meenakshi', 'address': 'Bannerghatta Road'},
            {'name': 'PVR Director Cut', 'address': 'Forum Mall, Koramangala'},
        ]
    },
    {
        'city': 'Chennai', 'state': 'Tamil Nadu',
        'theaters': [
            {'name': 'SPI Cinemas Luxe', 'address': 'Express Avenue Mall, Royapettah'},
            {'name': 'PVR Heritage RSL', 'address': 'ECR, Chennai'},
        ]
    },
    {
        'city': 'Delhi-NCR', 'state': 'Delhi',
        'theaters': [
            {'name': 'PVR Anupam', 'address': 'Saket, New Delhi'},
            {'name': 'Miraj Cinemas', 'address': 'V3S Mall, Laxmi Nagar'},
        ]
    },
    {
        'city': 'Kochi', 'state': 'Kerala',
        'theaters': [
            {'name': 'PVR Lulu Mall', 'address': 'Edappally, Kochi'},
        ]
    },
    {
        'city': 'Pune', 'state': 'Maharashtra',
        'theaters': [
            {'name': 'PVR Icon Pavilion', 'address': 'Senapati Bapat Road, Pune'},
        ]
    },
]


class Command(BaseCommand):
    help = "Synchronizes official Indian theatrical releases & blockbuster movies from TMDb API into Django database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--pages',
            type=int,
            default=2,
            help='Number of pages to fetch per category (default: 2).'
        )

    def success(self, msg: str) -> str:
        style_fn = getattr(self.style, 'SUCCESS', str)
        return str(style_fn(msg))

    def handle(self, *args, **options):
        pages = options.get('pages', 2)
        self.stdout.write(self.success(f"Starting Indian TMDb Movie Sync ({pages} pages per category)..."))

        # 1. Sync TMDb Genres
        self.sync_genres()

        # 2. Sync Indian Theatrical Categories with region='IN'
        categories = [
            ('now_playing', '/movie/now_playing'),
            ('popular', '/movie/popular'),
            ('top_rated', '/movie/top_rated'),
            ('upcoming', '/movie/upcoming'),
        ]

        total_imported = 0
        for category_name, endpoint in categories:
            for page in range(1, pages + 1):
                imported = self.import_category_page(category_name, endpoint, page, region='IN')
                total_imported += imported

        # 3. Sync Indian Regional Movies (Hindi, Telugu, Tamil, Malayalam, Kannada) via discover API
        indian_discover_count = self.import_indian_regional_movies(pages=pages)
        total_imported += indian_discover_count

        # 4. Generate Indian cities, theaters, screens & showtimes
        shows_created = self.generate_indian_theater_shows()

        self.stdout.write(self.success(
            f"Successfully synchronized {total_imported} official Indian TMDb movies and generated {shows_created} showtimes across Indian cities & theaters!"
        ))

    def sync_genres(self):
        data = tmdb_request('/genre/movie/list')
        if data and 'genres' in data:
            for g in data['genres']:
                Genre.objects.get_or_create(name=g['name'])

    def import_category_page(self, category_name, endpoint, page, region='IN'):
        params = {'page': page, 'region': region}
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

            # Requirement 1A: Filter out any movie where poster_path is null or empty
            poster_path = item.get('poster_path')
            if not poster_path:
                continue

            description = item.get('overview') or 'No plot overview available.'
            backdrop_path = item.get('backdrop_path')

            # Ensure valid TMDb image URL builder
            poster_clean = poster_path.lstrip('/')
            poster_url = f"https://image.tmdb.org/t/p/w500/{poster_clean}"
            backdrop_url = f"https://image.tmdb.org/t/p/w1280/{backdrop_path.lstrip('/')}" if backdrop_path else ''

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
            lang_code = item.get('original_language', 'en').lower()
            lang_name = INDIAN_LANG_MAP.get(lang_code, lang_code.upper())
            lang_obj, _ = Language.objects.get_or_create(code=lang_code, defaults={'name': lang_name})

            rating = round(item.get('vote_average', 7.5), 1)
            popularity = round(item.get('popularity', 50.0), 1)

            # Fetch official YouTube trailer from TMDb videos API (multi-language resilient)
            trailer_url = self.fetch_trailer_url(tmdb_id, orig_lang=lang_code)

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
            # Only set trailer_url if we found one (don't overwrite existing with empty)
            if trailer_url:
                defaults['trailer_url'] = trailer_url

            movie_obj, created = Movie.objects.update_or_create(
                tmdb_id=tmdb_id,
                defaults=defaults
            )

            # Assign genres
            genre_ids = item.get('genre_ids', [])
            if genre_ids:
                genre_objs = Genre.objects.filter(id__in=genre_ids)
                if genre_objs.exists():
                    movie_obj.genres.set(genre_objs)

            count += 1
            action_str = "Created" if created else "Updated"
            trailer_status = " [+trailer]" if trailer_url else ""
            safe_title = title.encode('ascii', 'replace').decode('ascii')
            self.stdout.write(self.success(f"{action_str} [{category_name}] {safe_title} ({lang_name} - TMDb #{tmdb_id}){trailer_status}"))

        return count

    def fetch_trailer_url(self, tmdb_id, orig_lang=None):
        """Fetch the official YouTube trailer URL for a movie from TMDb videos API with multi-language fallback."""
        from movies.utils.tmdb import get_movie_trailer_url
        return get_movie_trailer_url(tmdb_id, original_language=orig_lang) or ''


    def generate_indian_theater_shows(self):
        now = timezone.now()
        today = now.date()
        ninety_days_ago = today - datetime.timedelta(days=90)

        # Only schedule shows for current theatrical movies (released within 90 days or now_playing)
        movies = list(Movie.objects.filter(
            is_active=True
        ).exclude(
            poster_url__isnull=True
        ).exclude(
            poster_url=''
        ).filter(
            Q(category='now_playing') | Q(release_date__gte=ninety_days_ago, release_date__lte=today + datetime.timedelta(days=14))
        ))

        if not movies:
            return 0

        # Build Indian cities, theaters, and screens
        all_screens = []
        screen_types = ['IMAX_3D', '4DX', '2D', '3D']
        for cdata in INDIAN_CITIES_AND_THEATERS:
            city_name = cdata['city']
            city_state = cdata['state']
            city_obj = City.objects.filter(name__iexact=city_name).first()
            if not city_obj:
                city_obj = City.objects.create(name=city_name, state=city_state)
            theaters_list = cdata['theaters']
            if isinstance(theaters_list, list):
                for titem in theaters_list:
                    if isinstance(titem, dict):
                        t_name = titem['name']
                        t_addr = titem['address']
                        theater_obj, _ = Theater.objects.get_or_create(
                            name=t_name,
                            city=city_obj,
                            defaults={'address': t_addr}
                        )
                        for s_num in range(1, 3):
                            stype = screen_types[(s_num - 1) % len(screen_types)]
                            screen_obj, _ = Screen.objects.get_or_create(
                                theater=theater_obj,
                                name=f"Audi {s_num}",
                                defaults={'screen_type': stype, 'total_seats': 120}
                            )
                            all_screens.append(screen_obj)

        shows_created = 0
        for m_idx, movie in enumerate(movies):
            assigned_screen = all_screens[m_idx % len(all_screens)]
            for h_offset in [2, 5, 8, 26, 30, 50]:
                stime = (now + datetime.timedelta(hours=h_offset + m_idx)).replace(minute=0, second=0, microsecond=0)
                _, created = Show.objects.get_or_create(
                    screen=assigned_screen,
                    start_time=stime,
                    defaults={
                        'movie': movie,
                        'base_price': 250.00,
                        'available_seats': assigned_screen.total_seats,
                        'status': 'OPEN'
                    }
                )
                if created:
                    shows_created += 1

        return shows_created
