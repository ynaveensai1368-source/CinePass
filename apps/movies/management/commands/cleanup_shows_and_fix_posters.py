import datetime
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db.models import Q

from movies.models import Movie
from shows.models import Show

TMDB_API_KEY = getattr(settings, 'TMDB_API_KEY', '')
TMDB_ACCESS_TOKEN = getattr(settings, 'TMDB_ACCESS_TOKEN', '')
TMDB_BASE = 'https://api.themoviedb.org/3'


class Command(BaseCommand):
    help = "Cleans up future shows for older catalog movies and backfills missing poster artwork and trailers from TMDb API."

    def get_headers(self):
        headers = {'accept': 'application/json'}
        if TMDB_ACCESS_TOKEN:
            headers['Authorization'] = f'Bearer {TMDB_ACCESS_TOKEN}'
        return headers

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting CinePass Showtime Cleanup & Poster Backfill..."))

        # =========================================================================
        # 1. SHOWTIME CLEANUP FOR OLDER / NON-THEATRICAL MOVIES
        # =========================================================================
        now = timezone.now()
        today = now.date()
        ninety_days_ago = today - datetime.timedelta(days=90)

        # Movies released > 90 days ago or old catalog items
        old_movies = Movie.objects.filter(
            Q(release_date__lt=ninety_days_ago) & ~Q(category='now_playing')
        )

        deleted_shows_count, _ = Show.objects.filter(
            movie__in=old_movies,
            start_time__gte=now
        ).delete()

        self.stdout.write(self.style.SUCCESS(
            f"[1/2] Showtime Cleanup: Removed {deleted_shows_count} future shows from {old_movies.count()} older catalog movies."
        ))

        # =========================================================================
        # 2. POSTER BACKFILL & VALIDATION FROM TMDB API
        # =========================================================================
        all_movies = Movie.objects.all()
        updated_posters = 0
        inactivated_movies = 0

        for movie in all_movies:
            needs_update = not movie.poster_url or not movie.backdrop_url or not movie.trailer_url

            if needs_update and (TMDB_API_KEY or TMDB_ACCESS_TOKEN):
                # Search TMDb if tmdb_id is missing
                tmdb_id = movie.tmdb_id
                if not tmdb_id:
                    try:
                        search_url = f"{TMDB_BASE}/search/movie"
                        params = {'query': movie.title}
                        if TMDB_API_KEY:
                            params['api_key'] = TMDB_API_KEY
                        if movie.release_date:
                            params['year'] = movie.release_date.year

                        resp = requests.get(search_url, params=params, headers=self.get_headers(), timeout=8)
                        if resp.status_code == 200:
                            results = resp.json().get('results', [])
                            if results:
                                tmdb_id = results[0]['id']
                                movie.tmdb_id = tmdb_id
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Search failed for {movie.title}: {e}"))

                # Fetch movie details from TMDb
                if tmdb_id:
                    try:
                        detail_url = f"{TMDB_BASE}/movie/{tmdb_id}"
                        params = {'api_key': TMDB_API_KEY} if TMDB_API_KEY else {}
                        resp = requests.get(detail_url, params=params, headers=self.get_headers(), timeout=8)
                        if resp.status_code == 200:
                            data = resp.json()
                            poster_path = data.get('poster_path')
                            backdrop_path = data.get('backdrop_path')

                            if poster_path:
                                movie.poster_url = f"https://image.tmdb.org/t/p/w500/{poster_path.lstrip('/')}"
                            if backdrop_path:
                                movie.backdrop_url = f"https://image.tmdb.org/t/p/w1280/{backdrop_path.lstrip('/')}"
                            
                            if data.get('overview') and (not movie.description or movie.description == 'No plot overview available.'):
                                movie.description = data.get('overview')

                            updated_posters += 1
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Detail fetch failed for TMDb #{tmdb_id}: {e}"))

                    # Fetch authentic official YouTube video trailer from TMDb
                    try:
                        from movies.utils.tmdb import get_movie_trailer_data
                        lang_code = movie.language.code if movie.language else None
                        t_data = get_movie_trailer_data(tmdb_id, original_language=lang_code, title=movie.title)
                        if t_data and t_data.get('embed_url'):
                            movie.trailer_url = t_data['embed_url']
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f"Trailer fetch failed for TMDb #{tmdb_id}: {e}"))

            # If after all attempts a movie still has NO valid poster_url, mark is_active=False
            if not movie.poster_url:
                movie.is_active = False
                inactivated_movies += 1

            movie.save()

        self.stdout.write(self.style.SUCCESS(
            f"[2/2] Poster Backfill: Updated artwork/trailers for {updated_posters} movies. Inactivated {inactivated_movies} posterless movies."
        ))
        self.stdout.write(self.style.SUCCESS("All tasks completed successfully!"))
