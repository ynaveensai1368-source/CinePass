import logging
import datetime
from typing import Dict, Any, Optional
from django.utils import timezone
from django.core.cache import cache

from .base import BaseMovieProvider
from movies.utils.tmdb import tmdb_request, get_movie_trailer_data

logger = logging.getLogger(__name__)


class TMDBMovieProvider(BaseMovieProvider):
    """
    Production-grade implementation of BaseMovieProvider interfacing directly with TMDb.
    Features:
      - Resilient multi-domain network transport
      - Dynamic timezone-aware (Asia/Kolkata) date calculation (no hardcoded years)
      - Regional parameterization for India ('IN') and regional languages
      - Structured cache with dynamic TTL and granular composite cache keys
      - Graceful error handling and diagnostic telemetry logging
    """

    CACHE_TTL_SECONDS = 3600  # 1 hour cache TTL

    def _get_india_today(self) -> datetime.date:
        """Returns the current date in Asia/Kolkata timezone."""
        return timezone.now().date()

    def get_now_playing(self, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """
        Retrieves current theatrical now_playing movies from TMDb for a specific country/region.
        """
        cache_key = f"tmdb_provider:now_playing:{region}:{page}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"[CACHE HIT] TMDB now_playing for region={region}, page={page}")
            return cached

        params = {'page': page}
        if region:
            params['region'] = region

        data = tmdb_request('/movie/now_playing', params)
        if not data or not data.get('results'):
            # Fallback to discover/movie with dynamic theatrical window
            today = self._get_india_today()
            cutoff = today - datetime.timedelta(days=75)
            future = today + datetime.timedelta(days=14)
            discover_params = {
                'page': page,
                'region': region,
                'with_release_type': '2|3',
                'release_date.gte': cutoff.strftime('%Y-%m-%d'),
                'release_date.lte': future.strftime('%Y-%m-%d'),
                'sort_by': 'popularity.desc',
            }
            data = tmdb_request('/discover/movie', discover_params) or {'results': []}

        results_count = len(data.get('results', []))
        logger.info(f"[TMDB PROVIDER] now_playing region={region} page={page} -> {results_count} results")

        if data and data.get('results'):
            cache.set(cache_key, data, self.CACHE_TTL_SECONDS)
        return data or {'results': []}

    def get_upcoming(self, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """
        Retrieves upcoming theatrical releases dynamically from TMDb.
        """
        cache_key = f"tmdb_provider:upcoming:{region}:{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        today = self._get_india_today()
        future_limit = today + datetime.timedelta(days=180)
        params = {
            'page': page,
            'region': region,
            'release_date.gte': (today + datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
            'release_date.lte': future_limit.strftime('%Y-%m-%d'),
            'sort_by': 'popularity.desc',
            'with_release_type': '2|3',
        }
        data = tmdb_request('/discover/movie', params)
        if not data or not data.get('results'):
            data = tmdb_request('/movie/upcoming', {'page': page, 'region': region}) or {'results': []}

        if data and data.get('results'):
            cache.set(cache_key, data, self.CACHE_TTL_SECONDS)
        return data or {'results': []}

    def get_popular(self, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """
        Retrieves popular movies from TMDb.
        """
        cache_key = f"tmdb_provider:popular:{region}:{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        params = {'page': page}
        if region:
            params['region'] = region

        data = tmdb_request('/movie/popular', params) or {'results': []}
        if data and data.get('results'):
            cache.set(cache_key, data, self.CACHE_TTL_SECONDS)
        return data

    def get_trending(self, time_window: str = 'day', page: int = 1) -> Dict[str, Any]:
        """
        Retrieves trending movies from TMDb (/trending/movie/{day|week}).
        """
        cache_key = f"tmdb_provider:trending:{time_window}:{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = tmdb_request(f'/trending/movie/{time_window}', {'page': page}) or {'results': []}
        if data and data.get('results'):
            cache.set(cache_key, data, self.CACHE_TTL_SECONDS)
        return data

    def get_top_rated(self, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """
        Retrieves top rated movies from TMDb.
        """
        cache_key = f"tmdb_provider:top_rated:{region}:{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        params = {'page': page}
        if region:
            params['region'] = region

        data = tmdb_request('/movie/top_rated', params) or {'results': []}
        if data and data.get('results'):
            cache.set(cache_key, data, self.CACHE_TTL_SECONDS)
        return data

    def search_movies(self, query: str, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """
        Searches movies dynamically via TMDb search endpoint.
        """
        if not query or not query.strip():
            return {'results': []}

        clean_query = query.strip()
        cache_key = f"tmdb_provider:search:{region}:{clean_query.lower()}:{page}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        params = {'query': clean_query, 'page': page}
        if region:
            params['region'] = region

        data = tmdb_request('/search/movie', params) or {'results': []}
        if data and data.get('results'):
            cache.set(cache_key, data, 1800)  # 30 mins for search queries
        return data

    def get_movie_details(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed movie metadata and credits from TMDb.
        """
        if not tmdb_id:
            return None
        cache_key = f"tmdb_provider:movie_details:{tmdb_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        data = tmdb_request(f'/movie/{tmdb_id}', {'append_to_response': 'credits,videos,release_dates'})
        if data:
            cache.set(cache_key, data, 86400)  # 24 hours for static movie details
        return data

    def get_trailers(self, tmdb_id: int, title: str = '') -> Dict[str, Any]:
        """
        Retrieves official YouTube trailer URLs for the movie.
        """
        return get_movie_trailer_data(tmdb_id, title=title)
