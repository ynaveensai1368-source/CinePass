import re
import requests
import logging
from django.conf import settings
from django.core.cache import cache

import hashlib

logger = logging.getLogger(__name__)

TMDB_BASE_URL = getattr(settings, 'TMDB_BASE_URL', 'https://api.themoviedb.org/3')
TMDB_API_KEY = getattr(settings, 'TMDB_API_KEY', '')


def extract_youtube_id(url_or_id):
    """
    Extracts and validates a 11-character YouTube video ID from various URL formats.
    """
    if not url_or_id:
        return None

    # Direct 11-char ID check
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id

    # Pattern regex for YouTube URLs
    patterns = [
        r'(?:v=|\/embed\/|\/v\/|https?:\/\/youtu\.be\/|\/watch\?v=)([\w-]{11})',
        r'youtu\.be\/([\w-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return None


def get_safe_youtube_embed_url(url_or_id):
    """
    Returns a standard, high-compatibility YouTube embed URL to prevent Error 153.
    """
    video_id = extract_youtube_id(url_or_id)
    if video_id:
        return f"https://www.youtube.com/embed/{video_id}?enablejsapi=1&rel=0"
    return None


def get_youtube_watch_url(url_or_id):
    """
    Returns a direct YouTube watch URL for external fallback playback.
    """
    video_id = extract_youtube_id(url_or_id)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return url_or_id if url_or_id else '#'


def tmdb_request(endpoint, params=None):
    """
    Executes a cached HTTP GET request to TMDB API endpoints with connection pooling and retries.
    """
    from .utils.tmdb import tmdb_request as shared_tmdb_request
    return shared_tmdb_request(endpoint, params=params)


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


def get_now_playing_movies_tmdb(page=1, region='IN'):
    """
    Retrieves current theatrical now_playing movies from TMDb for a specific country/region (default: India 'IN').
    """
    params = {'page': page}
    if region:
        params['region'] = region
    return tmdb_request('/movie/now_playing', params)


def get_theatrical_discover_movies_tmdb(page=1, region='IN', language=None, start_date=None, end_date=None, sort_by='popularity.desc'):
    """
    Discovers active theatrical releases from TMDb with dynamic release window and regional language support.
    """
    import datetime
    from django.utils import timezone
    today = timezone.now().date()
    if not start_date:
        start_date = (today - datetime.timedelta(days=75)).isoformat()
    if not end_date:
        end_date = (today + datetime.timedelta(days=14)).isoformat()

    params = {
        'page': page,
        'region': region or 'IN',
        'with_release_type': '2|3',
        'primary_release_date.gte': start_date,
        'primary_release_date.lte': end_date,
        'sort_by': sort_by,
    }
    if language:
        params['with_original_language'] = language
    return tmdb_request('/discover/movie', params)


def sync_current_theatrical_catalog(force=False):
    """
    Synchronizes genuine current theatrical movies from TMDb for India (IN) across
    all regional Indian languages (Telugu, Tamil, Hindi, Malayalam, Kannada, Punjabi, Bengali, Marathi, Gujarati)
    and International (English, Japanese, Korean) theatrical releases.
    Automatically cleans up outdated shows and distributes active showtimes across Indian cities.
    """
    import datetime
    from decimal import Decimal
    from django.utils import timezone
    from django.utils.text import slugify
    from django.db.models import Q

    from movies.models import Movie, Language, Genre, Cast
    from movies.utils.images import normalize_image_url
    from movies.utils.tmdb import get_movie_trailer_url
    from theaters.models import City, Theater, Screen, Seat
    from shows.models import Show

    today = timezone.now().date()
    cache_key = f"cinepass_theatrical_sync_{today.isoformat()}"
    theatrical_cutoff = today - datetime.timedelta(days=75)
    theatrical_future_cutoff = today + datetime.timedelta(days=14)

    if not force and cache.get(cache_key):
        return Movie.objects.filter(is_active=True, category='now_playing', release_date__gte=theatrical_cutoff).count()

    logger.info(f"[PIPELINE] Starting TMDb Theatrical Synchronization for India (Region: IN, Today: {today})")
    start_date = theatrical_cutoff.isoformat()
    end_date = theatrical_future_cutoff.isoformat()

    results = []
    seen_ids = set()

    # 1. Fetch multiple pages from /movie/now_playing?region=IN
    for page_num in range(1, 4):
        try:
            now_playing_data = get_now_playing_movies_tmdb(page=page_num, region='IN')
            if now_playing_data and now_playing_data.get('results'):
                for item in now_playing_data['results']:
                    mid = item.get('id')
                    if mid and mid not in seen_ids:
                        seen_ids.add(mid)
                        results.append(item)
        except Exception as e:
            logger.warning(f"Failed fetching now_playing page {page_num}: {e}")

    logger.info(f"[PIPELINE] Fetched {len(results)} movies from /movie/now_playing?region=IN (pages 1-3)")

    # 2. Fetch from /discover/movie for regional Indian languages & international releases in India
    discover_langs = ['te', 'ta', 'hi', 'ml', 'kn', 'mr', 'pa', 'bn', 'gu', 'en', 'ja', 'ko']
    for lang in discover_langs:
        try:
            disc_data = get_theatrical_discover_movies_tmdb(
                page=1,
                region='IN',
                language=lang,
                start_date=start_date,
                end_date=end_date
            )
            if disc_data and disc_data.get('results'):
                for item in disc_data['results']:
                    mid = item.get('id')
                    if mid and mid not in seen_ids:
                        seen_ids.add(mid)
                        results.append(item)
        except Exception as e:
            logger.warning(f"Failed discover for language {lang}: {e}")

    logger.info(f"[PIPELINE] Total candidate theatrical releases after regional discover: {len(results)}")

    # 3. Filter candidates strictly by dynamic theatrical release dates and save/update in DB
    current_movie_objs = []
    for item in results:
        tmdb_id = item.get('id')
        title = item.get('title') or item.get('original_title')
        poster_path = item.get('poster_path')
        if not tmdb_id or not title or not poster_path:
            continue

        release_date = None
        if item.get('release_date'):
            try:
                release_date = datetime.datetime.strptime(item['release_date'], '%Y-%m-%d').date()
            except Exception:
                pass

        if not release_date:
            release_date = today

        # Validate that release date falls within current theatrical window
        if release_date < theatrical_cutoff or release_date > theatrical_future_cutoff:
            continue

        lang_code = str(item.get('original_language', 'en')).lower()
        lang_name = INDIAN_LANG_MAP.get(lang_code, lang_code.upper())
        lang_obj, _ = Language.objects.get_or_create(code=lang_code, defaults={'name': lang_name})

        poster_url = normalize_image_url(poster_path, size='w500', is_backdrop=False)
        backdrop_path = item.get('backdrop_path')
        backdrop_url = normalize_image_url(backdrop_path, size='w1280', is_backdrop=True) if backdrop_path else ''

        rating = Decimal(str(round(float(item.get('vote_average', 7.5)), 1)))
        popularity = int(round(float(item.get('popularity', 50.0))))
        description = item.get('overview') or 'No plot overview available.'
        tagline = item.get('tagline', '')

        trailer_url = get_movie_trailer_url(tmdb_id, original_language=lang_code) or ''

        defaults = {
            'title': title,
            'description': description,
            'poster_url': poster_url,
            'backdrop_url': backdrop_url,
            'category': 'now_playing',
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

        movie, _ = Movie.objects.update_or_create(tmdb_id=tmdb_id, defaults=defaults)

        # Genres
        genre_ids = item.get('genre_ids', [])
        if genre_ids:
            genre_objs = Genre.objects.filter(id__in=genre_ids)
            if genre_objs.exists():
                movie.genres.set(genre_objs)

        # Credits (Fetch during sync for top featured items; rest fetched dynamically on detail view)
        if len(current_movie_objs) <= 12:
            try:
                fetch_and_sync_movie_credits(movie, limit=6)
            except Exception:
                pass

        current_movie_objs.append(movie)

    # 4. Clean up older catalog movies: Mark category as 'popular' and remove stale future shows
    older_movies = Movie.objects.filter(release_date__lt=theatrical_cutoff, category='now_playing')
    older_updated_count = older_movies.update(category='popular')
    if older_updated_count > 0:
        logger.info(f"[PIPELINE] Re-categorized {older_updated_count} older movies from 'now_playing' to 'popular'.")

    # Remove future shows from movies released before current theatrical window
    Show.objects.filter(movie__release_date__lt=theatrical_cutoff, start_time__gte=timezone.now()).delete()

    # 5. Distribute live showtimes for current theatrical movies across all Indian cities
    generate_theatrical_shows_for_cities(current_movie_objs)

    cache.set(cache_key, True, timeout=7200)  # 2-hour cache
    logger.info(f"[PIPELINE] Successfully synchronized {len(current_movie_objs)} active theatrical releases for India.")
    return len(current_movie_objs)


def generate_theatrical_shows_for_cities(movies_list=None):
    """
    Distributes active showtimes across all Indian cities and screens for current theatrical movies.
    Ensures regional audio screenings and international English screenings.
    """
    import datetime
    from decimal import Decimal
    from django.utils import timezone
    from django.utils.text import slugify

    from movies.models import Movie, Language
    from theaters.models import City, Theater, Screen, Seat
    from shows.models import Show

    today = timezone.now().date()
    now = timezone.now().replace(minute=0, second=0, microsecond=0)
    seventy_five_days_ago = today - datetime.timedelta(days=75)

    if not movies_list:
        movies_list = list(Movie.objects.filter(
            is_active=True,
            category='now_playing',
            release_date__gte=seventy_five_days_ago
        ).select_related('language').prefetch_related('genres'))

    if not movies_list:
        return 0

    CITY_THEATERS_DATA = [
        ('Hyderabad', 'Telangana', ['te', 'hi', 'en', 'ta', 'ml', 'kn'], [
            ('Prasads Multiplex Large Screen', 'NTR Gardens, Necklace Road'),
            ('AMB Cinemas Gachibowli', 'Sarath City Capital Mall, Gachibowli'),
            ('PVR Next Galleria Mall', 'Panjagutta'),
            ('INOX GVK One Mall', 'Banjara Hills'),
        ]),
        ('Mumbai', 'Maharashtra', ['hi', 'mr', 'en', 'gu', 'te', 'ta'], [
            ('PVR ICON Infinity Mall', 'Link Road, Andheri West'),
            ('INOX Megaplex Inorbit Mall', 'Malad West'),
            ('Cinepolis Viviana Mall', 'Thane West'),
            ('PVR Phoenix Palladium', 'Lower Parel'),
        ]),
        ('Delhi-NCR', 'Delhi', ['hi', 'pa', 'en', 'te', 'ta'], [
            ('PVR Director\'s Cut Ambience Mall', 'Vasant Kunj, New Delhi'),
            ('Cinepolis DLF Avenue', 'Saket, New Delhi'),
            ('INOX Nehru Place', 'Nehru Place, New Delhi'),
            ('PVR Plaza', 'Connaught Place, New Delhi'),
        ]),
        ('Chennai', 'Tamil Nadu', ['ta', 'te', 'en', 'ml', 'hi'], [
            ('SPI Sathyam Cinemas', 'Royapettah, Chennai'),
            ('PVR VR Mall', 'Jawaharlal Nehru Road, Anna Nagar'),
            ('AGS Cinemas OMR', 'Navalur, Chennai'),
            ('INOX Marina Mall', 'Egattur, Chennai'),
        ]),
        ('Bengaluru', 'Karnataka', ['kn', 'te', 'ta', 'hi', 'en', 'ml'], [
            ('PVR IMAX Vega City Mall', 'Bannerghatta Road'),
            ('INOX Nexus Forum Mall', 'Koramangala'),
            ('Cinepolis Orion Mall', 'Rajajinagar'),
            ('PVR Phoenix Marketcity', 'Whitefield'),
        ]),
        ('Kochi', 'Kerala', ['ml', 'ta', 'en', 'hi', 'te'], [
            ('PVR Lulu Mall', 'Edappally, Kochi'),
            ('Shenoys Multiplex', 'MG Road, Kochi'),
            ('Cinepolis Centre Square Mall', 'MG Road, Kochi'),
        ]),
        ('Pune', 'Maharashtra', ['mr', 'hi', 'en', 'te'], [
            ('PVR Phoenix Marketcity Pune', 'Viman Nagar'),
            ('INOX Amanora Mall', 'Hadapsar, Pune'),
        ]),
        ('Kolkata', 'West Bengal', ['bn', 'hi', 'en'], [
            ('PVR Quest Mall', 'Syed Amir Ali Avenue, Park Circus'),
            ('INOX South City Mall', 'Prince Anwar Shah Road'),
        ]),
        ('Ahmedabad', 'Gujarat', ['gu', 'hi', 'en'], [
            ('PVR Acropolis Mall', 'Thaltej, SG Highway'),
            ('Cinepolis Alpha One Mall', 'Vastrapur'),
        ]),
    ]

    shows_created = 0
    prices = [Decimal('220.00'), Decimal('260.00'), Decimal('320.00'), Decimal('380.00')]

    for city_name, state_name, preferred_langs, theaters_list in CITY_THEATERS_DATA:
        city_slug = slugify(city_name)
        city_obj, _ = City.objects.get_or_create(name=city_name, defaults={'state': state_name, 'slug': city_slug})

        # Filter movies relevant to this city's languages + English blockbusters
        city_movies = [m for m in movies_list if m.language and m.language.code in preferred_langs]
        if not city_movies:
            city_movies = movies_list[:10]

        for tname, taddr in theaters_list:
            tslug = slugify(f"{tname}-{city_name}")
            theater_obj, _ = Theater.objects.get_or_create(
                name=tname,
                city=city_obj,
                defaults={'address': taddr, 'slug': tslug, 'is_active': True}
            )

            for s_num in range(1, 4):
                sname = f"Audi {s_num}" if s_num > 1 else "IMAX Laser Screen 1"
                screen_obj, _ = Screen.objects.get_or_create(
                    theater=theater_obj,
                    name=sname,
                    defaults={'total_seats': 74}
                )

                # Ensure seat matrix
                if screen_obj.seats.count() < 74:
                    seats = []
                    for row in ['A', 'B', 'C', 'D']:
                        for num in range(1, 11):
                            seats.append(Seat(screen=screen_obj, row=row, number=num, seat_type='REGULAR'))
                    for row in ['E', 'F']:
                        for num in range(1, 13):
                            seats.append(Seat(screen=screen_obj, row=row, number=num, seat_type='PREMIUM'))
                    for row in ['G']:
                        for num in range(1, 11):
                            seats.append(Seat(screen=screen_obj, row=row, number=num, seat_type='RECLINER'))
                    try:
                        Seat.objects.bulk_create(seats, ignore_conflicts=True)
                    except Exception:
                        pass

                # Schedule shows across 3 days
                for m_idx, movie in enumerate(city_movies):
                    for day_offset in range(3):
                        for hour_val in [11, 14, 18, 21]:
                            show_time = (now + datetime.timedelta(days=day_offset)).replace(hour=hour_val, minute=0, second=0)
                            if show_time < timezone.now():
                                continue
                            end_time = show_time + datetime.timedelta(minutes=movie.duration + 20)
                            price = prices[(m_idx + s_num) % len(prices)]
                            show_obj, created = Show.objects.get_or_create(
                                screen=screen_obj,
                                start_time=show_time,
                                defaults={
                                    'movie': movie,
                                    'language': movie.language,
                                    'end_time': end_time,
                                    'base_price': price,
                                    'available_seats': screen_obj.total_seats,
                                    'status': 'OPEN'
                                }
                            )
                            if created:
                                shows_created += 1

    return shows_created


def fetch_movie_trailer_tmdb(tmdb_id, original_language=None):
    """
    Fetches the official YouTube trailer embed URL from TMDb using multi-language resilience.
    """
    from .utils.tmdb import get_movie_trailer_url
    return get_movie_trailer_url(tmdb_id, original_language) or ''


def fetch_and_sync_movie_credits(movie, limit=8):
    """
    Fetches cast & director credits from TMDb /movie/{id}/credits and associates them with the Movie instance.
    """
    if not movie.tmdb_id:
        return
    data = tmdb_request(f'/movie/{movie.tmdb_id}/credits')
    if not data:
        return

    from movies.models import Cast
    
    # 1. Director
    crew = data.get('crew', [])
    directors = [c['name'] for c in crew if c.get('job') == 'Director']
    if directors and not movie.director:
        movie.director = ', '.join(directors[:2])
        movie.save(update_fields=['director'])

    # 2. Cast members
    cast_list = data.get('cast', [])[:limit]
    for citem in cast_list:
        person_id = citem.get('id')
        name = citem.get('name')
        character = citem.get('character', '')
        profile_path = citem.get('profile_path')
        profile_url = f"https://image.tmdb.org/t/p/w185/{profile_path.lstrip('/')}" if profile_path else ''

        if person_id and name:
            cast_obj, _ = Cast.objects.get_or_create(
                tmdb_id=person_id,
                defaults={
                    'name': name,
                    'character_name': character,
                    'profile_image_url': profile_url
                }
            )
            if character and not cast_obj.character_name:
                cast_obj.character_name = character
                cast_obj.save(update_fields=['character_name'])
            movie.cast_members.add(cast_obj)
