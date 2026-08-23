import time
from django.core.management.base import BaseCommand
from django.db.models import Q
from movies.models import Movie
from movies.utils.tmdb import get_movie_trailer_data, get_movie_trailer_url, search_tmdb_movie_id


class Command(BaseCommand):
    help = "Resiliently synchronizes and backfills YouTube trailers for movies using TMDb API multi-language discovery."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-fetch and overwrite trailers for all movies, clearing invalid ones.'
        )
        parser.add_argument(
            '--missing-only',
            action='store_true',
            default=False,
            help='Only process movies with missing or empty trailer_url.'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Maximum number of movies to process.'
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        limit = options.get('limit')

        if force:
            qs = Movie.objects.filter(is_active=True)
            self.stdout.write(self.style.WARNING("Force mode enabled: Checking and auditing all active movies..."))
        else:
            qs = Movie.objects.filter(is_active=True).filter(
                Q(trailer_url__isnull=True) | Q(trailer_url='')
            )
            self.stdout.write(self.style.NOTICE(f"Missing-only mode: Found {qs.count()} active movies needing trailers."))

        if limit:
            qs = qs[:limit]

        movies = list(qs.select_related('language'))
        total = len(movies)
        updated_count = 0
        cleared_count = 0
        not_found_count = 0

        self.stdout.write(self.style.SUCCESS(f"Starting trailer synchronization for {total} movies...\n"))

        for i, movie in enumerate(movies, 1):
            title_safe = movie.title.encode('ascii', 'replace').decode('ascii')
            lang_code = movie.language.code if movie.language else None

            # If tmdb_id is missing, search TMDb by title & release year
            if not movie.tmdb_id:
                year = movie.release_date.year if movie.release_date else None
                found_id = search_tmdb_movie_id(movie.title, release_year=year)
                if found_id:
                    movie.tmdb_id = found_id
                    movie.save(update_fields=['tmdb_id'])

            if not movie.tmdb_id:
                self.stdout.write(self.style.WARNING(f"[{i}/{total}] {title_safe}: Skipped (No TMDb ID)"))
                not_found_count += 1
                continue

            # Resilient multi-language trailer discovery for this exact TMDb movie ID
            t_data = get_movie_trailer_data(movie.tmdb_id, original_language=lang_code, title=movie.title)

            if t_data and t_data.get('embed_url'):
                if movie.trailer_url != t_data['embed_url']:
                    movie.trailer_url = t_data['embed_url']
                    movie.save(update_fields=['trailer_url'])
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f"[{i}/{total}] {title_safe} ({lang_code}): Updated -> [{t_data['type']}] {t_data['name']} ({t_data['key']})"))
                else:
                    self.stdout.write(self.style.NOTICE(f"[{i}/{total}] {title_safe} ({lang_code}): Already accurate ({t_data['key']})"))
            else:
                if movie.trailer_url and force:
                    movie.trailer_url = ''
                    movie.save(update_fields=['trailer_url'])
                    cleared_count += 1
                    self.stdout.write(self.style.WARNING(f"[{i}/{total}] {title_safe} ({lang_code}): Cleared invalid trailer (none on TMDb)"))
                else:
                    not_found_count += 1
                    self.stdout.write(self.style.NOTICE(f"[{i}/{total}] {title_safe} ({lang_code}): No trailer on TMDb"))


            # Rate limit protection
            if i % 30 == 0:
                time.sleep(1)

        self.stdout.write(self.style.SUCCESS(
            f"\nTrailer Synchronization Complete!\n"
            f"  - Successfully updated: {updated_count}\n"
            f"  - No trailer available: {not_found_count}\n"
            f"  - Total processed: {total}"
        ))
