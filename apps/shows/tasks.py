import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction

from .models import SeatReservation, ShowSeat
from .consumers import broadcast_seat_status_change

logger = logging.getLogger(__name__)


@shared_task
def expire_seat_reservations():
    """
    Periodic background Celery task to clean up expired 2-minute seat reservations in bulk.
    Finds ACTIVE / RESERVED reservations where expires_at <= now(), updates status to EXPIRED,
    resets associated ShowSeat records back to AVAILABLE, and broadcasts WebSocket updates.
    """
    now = timezone.now()
    expired_reservations = list(
        SeatReservation.objects.filter(
            status__in=['ACTIVE', 'RESERVED'],
            expires_at__lte=now
        ).select_related('show')
    )

    if not expired_reservations:
        return 0

    with transaction.atomic():
        expired_ids = [res.id for res in expired_reservations]

        # Get seat labels to broadcast WebSocket event
        released_show_seats = list(
            ShowSeat.objects.filter(
                reservation_id__in=expired_ids,
                status='RESERVED'
            ).select_related('seat')
        )

        show_seat_map = {}
        for ss in released_show_seats:
            if ss.show_id not in show_seat_map:
                show_seat_map[ss.show_id] = []
            show_seat_map[ss.show_id].append(f"{ss.seat.row}{ss.seat.number}")

        # Reset corresponding ShowSeats back to AVAILABLE
        released_seats = ShowSeat.objects.filter(
            reservation_id__in=expired_ids,
            status='RESERVED'
        ).update(
            status='AVAILABLE',
            reservation=None
        )

        # Bulk update reservation status to EXPIRED
        updated_count = SeatReservation.objects.filter(id__in=expired_ids).update(status='EXPIRED')

        # Broadcast WebSocket updates per show
        for show_id, seat_labels in show_seat_map.items():
            broadcast_seat_status_change(show_id, seat_labels, 'AVAILABLE')

        logger.info(f"Cleaned up {updated_count} expired seat reservations and released {released_seats} seats.")
        return updated_count
