from .base import BaseMovieProvider, BaseTheaterProvider, BaseBookingProvider
from .tmdb_provider import TMDBMovieProvider
from .theater_provider import DatabaseTheaterProvider
from .booking_provider import CinePassBookingProvider

# Default singleton provider instances
movie_provider = TMDBMovieProvider()
theater_provider = DatabaseTheaterProvider()
booking_provider = CinePassBookingProvider()

__all__ = [
    'BaseMovieProvider',
    'BaseTheaterProvider',
    'BaseBookingProvider',
    'TMDBMovieProvider',
    'DatabaseTheaterProvider',
    'CinePassBookingProvider',
    'movie_provider',
    'theater_provider',
    'booking_provider',
]
