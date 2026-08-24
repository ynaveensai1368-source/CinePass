from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class BaseMovieProvider(ABC):
    """
    Abstract Base Class defining the contract for dynamic movie metadata and discovery providers (e.g. TMDb).
    """

    @abstractmethod
    def get_now_playing(self, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """Retrieve current theatrical now-playing releases."""
        pass

    @abstractmethod
    def get_upcoming(self, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """Retrieve upcoming future theatrical releases."""
        pass

    @abstractmethod
    def get_popular(self, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """Retrieve globally/regionally popular releases."""
        pass

    @abstractmethod
    def get_trending(self, time_window: str = 'day', page: int = 1) -> Dict[str, Any]:
        """Retrieve daily/weekly trending movies."""
        pass

    @abstractmethod
    def get_top_rated(self, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """Retrieve top-rated releases."""
        pass

    @abstractmethod
    def search_movies(self, query: str, region: str = 'IN', page: int = 1) -> Dict[str, Any]:
        """Search movies dynamically by title, keyword, or actor."""
        pass

    @abstractmethod
    def get_movie_details(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve rich movie metadata and synopsis."""
        pass

    @abstractmethod
    def get_trailers(self, tmdb_id: int, title: str = '') -> Dict[str, Any]:
        """Retrieve official video trailer links."""
        pass


class BaseTheaterProvider(ABC):
    """
    Abstract Base Class defining the contract for cinema theater directory and venue providers.
    """

    @abstractmethod
    def get_theaters_for_city(self, city_id_or_name: Any) -> List[Any]:
        """Retrieve list of cinema theaters located in the specified city."""
        pass

    @abstractmethod
    def get_theater_details(self, theater_id: int) -> Optional[Any]:
        """Retrieve theater venue metadata (address, screens, coordinates)."""
        pass


class BaseBookingProvider(ABC):
    """
    Abstract Base Class defining the contract for real-time cinema showtime and ticket booking providers.
    Separates genuine booking availability from movie metadata.
    """

    @abstractmethod
    def get_active_shows(self, movie_id: int, city_id: Optional[int] = None) -> List[Any]:
        """Retrieve legitimate active showtimes with available seats."""
        pass

    @abstractmethod
    def has_booking_availability(self, movie_id: int, city_id: Optional[int] = None) -> bool:
        """Determines if authentic bookable tickets exist for the movie in the specified city."""
        pass
