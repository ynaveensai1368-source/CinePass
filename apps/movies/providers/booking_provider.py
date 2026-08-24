import logging
from typing import List, Any, Optional
from django.utils import timezone
from django.db.models import Q

from .base import BaseBookingProvider
from shows.models import Show

logger = logging.getLogger(__name__)


class CinePassBookingProvider(BaseBookingProvider):
    """
    Production implementation of BaseBookingProvider.
    Validates authentic cinema showtime and seat availability in the CinePass database.
    Guarantees that ticket availability is NEVER fabricated or inferred from TMDB data.
    """

    def get_active_shows(self, movie_id: int, city_id: Optional[int] = None) -> List[Show]:
        """
        Retrieves real open showtimes for a movie in the given city with available seats.
        """
        now = timezone.now()
        qs = Show.objects.filter(
            movie_id=movie_id,
            start_time__gte=now,
            status='OPEN',
            available_seats__gt=0
        ).select_related('screen__theater__city', 'screen__theater', 'screen', 'language')

        if city_id:
            qs = qs.filter(screen__theater__city_id=city_id)

        return list(qs.order_by('start_time', 'screen__theater__name'))

    def has_booking_availability(self, movie_id: int, city_id: Optional[int] = None) -> bool:
        """
        Returns True ONLY if authentic, bookable open showtimes exist in the specified city.
        """
        now = timezone.now()
        qs = Show.objects.filter(
            movie_id=movie_id,
            start_time__gte=now,
            status='OPEN',
            available_seats__gt=0
        )
        if city_id:
            qs = qs.filter(screen__theater__city_id=city_id)

        return qs.exists()
