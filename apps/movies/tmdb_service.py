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
    Executes a cached HTTP GET request to TMDB API endpoints.
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
        access_token = getattr(settings, 'TMDB_ACCESS_TOKEN', '')
        if access_token:
            headers['Authorization'] = f"Bearer {access_token}"

        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            cache.set(cache_key, data, timeout=3600)  # Cache for 1 hour
            return data
    except Exception as e:
        logger.error(f"TMDB API request failed for {endpoint}: {e}")

    return None


def get_popular_movies_tmdb(page=1):
    return tmdb_request('/movie/popular', {'page': page})


def get_movie_videos_tmdb(tmdb_id):
    return tmdb_request(f'/movie/{tmdb_id}/videos')


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
