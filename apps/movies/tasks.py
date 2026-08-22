"""
Celery asynchronous tasks for CinePass movie catalog synchronization.
"""
import logging
from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def sync_tmdb_movies_task(self, pages=2):
    """
    Periodic task to automatically sync latest movies, posters, trailers, and showtimes from TMDb.
    """
    logger.info(f"Starting Celery periodic TMDb movie synchronization (pages={pages})...")
    try:
        call_command('sync_movies', pages=pages)
        logger.info("TMDb movie synchronization task completed successfully.")
        return True
    except Exception as exc:
        logger.error(f"Error during TMDb movie synchronization task: {exc}")
        raise self.retry(exc=exc)
