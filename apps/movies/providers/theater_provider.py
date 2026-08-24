import logging
from typing import List, Any, Optional
from django.core.cache import cache

from .base import BaseTheaterProvider
from theaters.models import Theater, City

logger = logging.getLogger(__name__)


class DatabaseTheaterProvider(BaseTheaterProvider):
    """
    Production implementation of BaseTheaterProvider querying the CinePass venue repository.
    Enforces city-level theater isolation, active status validation, and caching.
    """

    CACHE_TTL_SECONDS = 3600

    def get_theaters_for_city(self, city_id_or_name: Any) -> List[Theater]:
        """
        Retrieves list of active cinema theaters located in the specified city.
        """
        if not city_id_or_name:
            return list(Theater.objects.filter(is_active=True).select_related('city').order_by('name'))

        cache_key = f"theater_provider:city:{city_id_or_name}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        city_obj = None
        if isinstance(city_id_or_name, int) or (isinstance(city_id_or_name, str) and city_id_or_name.isdigit()):
            city_obj = City.objects.filter(id=int(city_id_or_name)).first()
        elif isinstance(city_id_or_name, str):
            city_obj = City.objects.filter(name__iexact=city_id_or_name).first() or City.objects.filter(slug__iexact=city_id_or_name).first()
        elif isinstance(city_id_or_name, City):
            city_obj = city_id_or_name

        if city_obj:
            theaters = list(Theater.objects.filter(city=city_obj, is_active=True).order_by('name'))
        else:
            theaters = list(Theater.objects.filter(is_active=True).select_related('city').order_by('name'))

        cache.set(cache_key, theaters, self.CACHE_TTL_SECONDS)
        return theaters

    def get_theater_details(self, theater_id: int) -> Optional[Theater]:
        """
        Retrieves details and active screens for the specified theater.
        """
        return Theater.objects.filter(id=theater_id, is_active=True).select_related('city').prefetch_related('screens').first()
