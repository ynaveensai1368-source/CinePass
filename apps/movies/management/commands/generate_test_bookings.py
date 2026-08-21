import random
import uuid
import time
from decimal import Decimal
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from bookings.models import Booking
from shows.models import Show

User = get_user_model()


class Command(BaseCommand):
    help = 'Generates 100,000+ realistic benchmark booking records efficiently for performance testing.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=100000,
            help='Total number of booking records to generate (default: 100000).'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=5000,
            help='Batch size for bulk_create (default: 5000).'
        )

    def handle(self, *args, **options):
        total_count = options['count']
        batch_size = options['batch_size']

        self.stdout.write(self.style.SUCCESS(f"Starting generation of {total_count} benchmark booking records..."))
        start_time = time.time()


        # Fetch prerequisite shows and users
        shows = list(Show.objects.all())
        if not shows:
            self.stdout.write(self.style.ERROR("No shows found in database. Please run 'python manage.py seed_demo_data' first."))
            return

        users = list(User.objects.all())
        if not users:
            test_user = User.objects.create_user(username='bench_user', email='bench@cinepass.com', password='Password123')
            users = [test_user]

        statuses = ['CONFIRMED', 'CONFIRMED', 'CONFIRMED', 'CONFIRMED', 'CANCELLED', 'PENDING']
        now = timezone.now()

        created_records = 0
        batch_objects = []

        for i in range(1, total_count + 1):
            show = random.choice(shows)
            user = random.choice(users)
            seats = random.randint(1, 4)
            unit_price = show.base_price or Decimal('200.00')
            subtotal = unit_price * seats
            fee = Decimal('30.00')
            grand_total = subtotal + fee
            status = random.choice(statuses)

            # Distribute timestamps randomly over the past 365 days
            days_offset = random.randint(0, 365)
            hours_offset = random.randint(0, 23)
            minutes_offset = random.randint(0, 59)
            created_at = now - timedelta(days=days_offset, hours=hours_offset, minutes=minutes_offset)

            booking_number = f"CP-{i:08d}-{uuid.uuid4().hex[:4].upper()}"


            b = Booking(
                booking_number=booking_number,
                user=user,
                show=show,
                total_seats=seats,
                total_price=subtotal,
                convenience_fee=fee,
                grand_total=grand_total,
                status=status,
                created_at=created_at,
                updated_at=created_at
            )
            batch_objects.append(b)

            if len(batch_objects) >= batch_size or i == total_count:
                Booking.objects.bulk_create(batch_objects)
                created_records += len(batch_objects)
                batch_objects = []
                self.stdout.write(f"Generated {created_records}/{total_count} records...")

        elapsed = round(time.time() - start_time, 2)
        self.stdout.write(self.style.SUCCESS(f"Benchmark test data generation complete! Successfully created {created_records} bookings in {elapsed}s."))

