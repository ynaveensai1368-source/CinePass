from django.core.management.base import BaseCommand
from movies.catalog import seed_production_catalog


class Command(BaseCommand):
    help = "Seed database with rich production-ready sample genres, languages, cities, theaters, screens, seats, movies, and active shows."

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting CinePass production-ready database seeding..."))
        count = seed_production_catalog()
        self.stdout.write(self.style.SUCCESS(f"Successfully seeded CinePass database with {count} movies, theaters, screens, and shows!"))
