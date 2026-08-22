from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Synchronizes official TMDb releases & blockbuster movies into Django database (alias for sync_movies)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--pages',
            type=int,
            default=2,
            help='Number of pages to fetch per category (default: 2).'
        )
        parser.add_argument(
            '--repair-only',
            action='store_true',
            help='Only repair existing movie records without fetching new catalog pages.'
        )

    def handle(self, *args, **options):
        pages = options.get('pages', 2)
        repair_only = options.get('repair_only', False)
        call_command('sync_movies', pages=pages, repair_only=repair_only, stdout=self.stdout)
