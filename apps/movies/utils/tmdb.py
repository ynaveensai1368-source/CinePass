"""
Resilient TMDb API Utility for Movie Metadata, Videos & Credits.
Provides multi-language fallback querying, strict trailer priority selection, and safe embed generation.
"""
import re
import hashlib
import logging
import urllib.parse
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TMDB_BASE_URL = getattr(settings, 'TMDB_BASE_URL', 'https://api.themoviedb.org/3')
TMDB_API_KEY = getattr(settings, 'TMDB_API_KEY', '')
TMDB_ACCESS_TOKEN = getattr(settings, 'TMDB_ACCESS_TOKEN', '')

# Comprehensive Indian regional and global language codes for video search
VIDEO_LANGUAGES = 'en,hi,ta,te,ml,kn,mr,bn,pa,gu,ru,ko,es,ja,fr,de,it,null'

# Blacklist keywords to avoid fan-made videos, interviews, reactions, bloopers, etc.
DISALLOWED_VIDEO_KEYWORDS = [
    'interview', 'review', 'reaction', 'fan made', 'fan-made', 'concept', 
    'behind the scenes', 'poojai', 'bloopers', 'podcast', 'unboxing', 'tribute'
]


def extract_youtube_id(url_or_id):
    """
    Extracts and validates an 11-character YouTube video ID from various URL formats or direct IDs.
    """
    if not url_or_id:
        return None

    url_or_id = str(url_or_id).strip()

    # Direct 11-char ID check
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id

    # Pattern regex for various YouTube URL forms
    patterns = [
        r'(?:v=|\/embed\/|\/v\/|https?:\/\/youtu\.be\/|\/watch\?v=)([\w-]{11})',
        r'youtu\.be\/([\w-]{11})',
        r'youtube\.com\/shorts\/([\w-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)

    return None


def get_safe_youtube_embed_url(url_or_id):
    """
    Returns a standard, clean YouTube embed URL.
    Omits enablejsapi to prevent YouTube Error 153 (video player configuration error).
    """
    video_id = extract_youtube_id(url_or_id)
    if video_id:
        return f"https://www.youtube.com/embed/{video_id}?autoplay=1"
    return None




def get_youtube_watch_url(url_or_id, title=None):
    """
    Returns a direct YouTube watch URL for external fallback playback.
    Returns empty string if no valid video ID exists.
    """
    video_id = extract_youtube_id(url_or_id)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    return ''


_session = None

def get_tmdb_session():
    global _session
    if _session is None:
        _session = requests.Session()
        from urllib3.util import Retry
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20, max_retries=retries)
        _session.mount('https://', adapter)
        _session.mount('http://', adapter)
    return _session


def tmdb_request(endpoint, params=None):
    """
    Executes a cached HTTP GET request to TMDB API endpoints with sanitized cache keys.
    """
    if params is None:
        params = {}

    if TMDB_API_KEY:
        params['api_key'] = TMDB_API_KEY

    param_str = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
    param_hash = hashlib.md5(param_str.encode('utf-8')).hexdigest()
    clean_endpoint = endpoint.strip('/').replace('/', '_')
    cache_key = f"tmdb_{clean_endpoint}_{param_hash}"

    cached_res = cache.get(cache_key)
    if cached_res:
        return cached_res

    try:
        url = f"{TMDB_BASE_URL}/{endpoint.lstrip('/')}"
        headers = {'accept': 'application/json'}
        if TMDB_ACCESS_TOKEN:
            headers['Authorization'] = f"Bearer {TMDB_ACCESS_TOKEN}"

        session = get_tmdb_session()
        response = session.get(url, params=params, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            cache.set(cache_key, data, timeout=3600)  # Cache for 1 hour
            return data
    except Exception as e:
        logger.error(f"TMDB API request failed for {endpoint}: {e}")

    return None


def _calculate_video_score(video, original_language=None):
    """
    Calculates a strict relevance score for a video item to pick the primary official trailer.
    Higher score indicates higher priority. Discards non-trailer videos.
    """
    name = str(video.get('name', '')).lower()
    vtype = str(video.get('type', ''))
    is_official = video.get('official') is True
    lang = str(video.get('iso_639_1', '')).lower()

    # Discard non-YouTube or missing key videos
    if str(video.get('site', '')).lower() != 'youtube' or not video.get('key'):
        return -1

    # Discard non-trailer video types (Clips, Featurettes, Behind the scenes, etc.)
    if vtype not in ('Trailer', 'Teaser'):
        return -1

    for blocked in DISALLOWED_VIDEO_KEYWORDS:
        if blocked in name:
            return -1

    score = 0

    # Type & Official Status Priority Hierarchy
    if vtype == 'Trailer':
        score += 1000 if is_official else 500
        if 'official trailer' in name:
            score += 100
        elif 'main trailer' in name:
            score += 75
        elif 'final trailer' in name:
            score += 60
        elif 'trailer' in name:
            score += 30
    elif vtype == 'Teaser':
        score += 200 if is_official else 100
        if 'official teaser' in name:
            score += 50
        elif 'teaser trailer' in name:
            score += 40
        elif 'teaser' in name:
            score += 20

    # Language match bonuses
    if original_language and lang == str(original_language).lower():
        score += 50
    elif lang == 'en':
        score += 25

    return score


def get_movie_trailer_data(tmdb_id, original_language=None, title=None):
    """
    Resilient multi-priority YouTube trailer discovery for any movie using its unique TMDb ID.
    Returns a dictionary containing:
      - 'key': 11-char YouTube ID
      - 'embed_url': Safe embed URL
      - 'watch_url': Direct YouTube watch URL
      - 'name': Video title
      - 'type': Video type (Trailer/Teaser/etc.)
      - 'is_official': Boolean
    Returns None if no valid video exists.
    """
    if not tmdb_id:
        return None

    # Strategy 1: Query with broad multi-language video parameters
    params = {'include_video_language': VIDEO_LANGUAGES}
    data = tmdb_request(f'/movie/{tmdb_id}/videos', params)
    results = data.get('results', []) if data else []

    # Strategy 2: If empty and original_language is provided, query specifically for that language
    if not results and original_language:
        data_lang = tmdb_request(f'/movie/{tmdb_id}/videos', {'language': original_language})
        if data_lang and data_lang.get('results'):
            results = data_lang['results']

    # Strategy 3: Plain fallback (default endpoint behavior)
    if not results:
        data_plain = tmdb_request(f'/movie/{tmdb_id}/videos')
        if data_plain and data_plain.get('results'):
            results = data_plain['results']

    if not results:
        return None

    # Score and rank all candidate videos
    scored_videos = []
    for v in results:
        score = _calculate_video_score(v, original_language)
        if score > 0:
            scored_videos.append((score, v))

    if not scored_videos:
        return None

    # Sort descending by score
    scored_videos.sort(key=lambda x: x[0], reverse=True)
    best_video = scored_videos[0][1]
    key = best_video.get('key')

    if not key or not extract_youtube_id(key):
        return None

    return {
        'key': key,
        'embed_url': get_safe_youtube_embed_url(key),
        'watch_url': get_youtube_watch_url(key, title=title),
        'name': best_video.get('name', 'Official Trailer'),
        'type': best_video.get('type', 'Trailer'),
        'is_official': best_video.get('official', False),
    }


def get_movie_trailer_key(tmdb_id, original_language=None):
    """
    Returns the YouTube video key (e.g., 'Mzw2ttJD2qQ') or None.
    """
    data = get_movie_trailer_data(tmdb_id, original_language)
    return data['key'] if data else None


def get_movie_trailer_url(tmdb_id, original_language=None):
    """
    Returns the ready-to-embed YouTube URL for a movie, or None if no video found.
    """
    data = get_movie_trailer_data(tmdb_id, original_language)
    return data['embed_url'] if data else None


def search_tmdb_movie_id(title, release_year=None):
    """
    Searches TMDb for a movie by title and optional release year, returning its exact TMDb ID.
    """
    if not title:
        return None
    params = {'query': title}
    if release_year:
        params['year'] = release_year

    data = tmdb_request('/search/movie', params)
    if data and data.get('results'):
        return data['results'][0]['id']
    return None
