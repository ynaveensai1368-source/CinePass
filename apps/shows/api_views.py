import uuid
import logging
from datetime import timedelta
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction, models
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Show, ShowSeat, SeatReservation
from theaters.models import Seat, Screen

logger = logging.getLogger(__name__)

# Price Multipliers per Tier
SEAT_TIER_PRICES = {
    'REGULAR': Decimal('1.0'),
    'PREMIUM': Decimal('1.4'),
    'VIP': Decimal('1.8'),
    'RECLINER': Decimal('2.2'),
}


def lazy_clean_expired_reservations(show=None):
    """
    Lazily cleans up expired reservations before availability check.
    """
    now = timezone.now()
    qs = SeatReservation.objects.filter(
        status__in=['ACTIVE', 'RESERVED'],
        expires_at__lte=now
    )
    if show:
        qs = qs.filter(show=show)

    expired_ids = list(qs.values_list('id', flat=True))
    if expired_ids:
        with transaction.atomic():
            ShowSeat.objects.filter(
                reservation_id__in=expired_ids,
                status='RESERVED'
            ).update(status='AVAILABLE', reservation=None)

            SeatReservation.objects.filter(id__in=expired_ids).update(status='EXPIRED')


def ensure_show_seats_initialized(show):
    """
    Ensures physical Seat and per-show ShowSeat records exist for a given Show.
    If physical Seats are missing on Screen, seeds standard 60-seat layout (Rows A-F, 10 seats/row).
    """
    screen = show.screen
    physical_seats = list(Seat.objects.filter(screen=screen, is_active=True))

    if not physical_seats:
        # Seed physical seats for Screen
        new_seats = []
        rows = ['A', 'B', 'C', 'D', 'E', 'F']
        for r_idx, r_letter in enumerate(rows):
            seat_type = 'VIP' if r_idx >= 4 else ('PREMIUM' if r_idx >= 2 else 'REGULAR')
            for num in range(1, 11):
                new_seats.append(Seat(
                    screen=screen,
                    row=r_letter,
                    number=num,
                    seat_type=seat_type,
                    is_active=True
                ))
        Seat.objects.bulk_create(new_seats, ignore_conflicts=True)
        physical_seats = list(Seat.objects.filter(screen=screen, is_active=True))

    # Seed ShowSeat records for this Show if missing
    existing_show_seat_ids = set(ShowSeat.objects.filter(show=show).values_list('seat_id', flat=True))
    base_price = show.base_price or Decimal('250.00')

    missing_show_seats = []
    for seat in physical_seats:
        if seat.id not in existing_show_seat_ids:
            multiplier = SEAT_TIER_PRICES.get(seat.seat_type, Decimal('1.0'))
            seat_price = (base_price * multiplier).quantize(Decimal('0.01'))
            missing_show_seats.append(ShowSeat(
                show=show,
                seat=seat,
                status='AVAILABLE',
                price=seat_price
            ))

    if missing_show_seats:
        ShowSeat.objects.bulk_create(missing_show_seats, ignore_conflicts=True)


class ShowSeatLayoutAPIView(View):
    """
    GET /api/shows/<show_id>/seats/
    Returns layout grid, row mapping, pricing, and live availability statuses.
    """
    def get(self, request, show_id):
        show = get_object_or_404(
            Show.objects.select_related('movie', 'screen__theater', 'screen__theater__city'),
            pk=show_id
        )

        # Lazy cleanup of expired reservations for this show
        lazy_clean_expired_reservations(show=show)
        ensure_show_seats_initialized(show)

        show_seats = ShowSeat.objects.filter(show=show).select_related('seat', 'reservation')

        # Active user reservation (if any)
        user_reservation = None
        if request.user.is_authenticated:
            user_reservation = SeatReservation.objects.filter(
                show=show,
                user=request.user,
                status__in=['ACTIVE', 'RESERVED'],
                expires_at__gt=timezone.now()
            ).first()

        seats_data = []
        now = timezone.now()

        for ss in show_seats:
            seat_status = ss.status.lower()

            # Dynamic status check against expired reservations
            if ss.status == 'RESERVED' and ss.reservation:
                if ss.reservation.expires_at <= now or ss.reservation.status == 'EXPIRED':
                    seat_status = 'available'
                elif request.user.is_authenticated and ss.reservation.user_id == request.user.id:
                    seat_status = 'user_selected'

            seats_data.append({
                'show_seat_id': ss.id,
                'seat_id': ss.seat.id,
                'row': ss.seat.row,
                'number': ss.seat.number,
                'label': f"{ss.seat.row}{ss.seat.number}",
                'type': ss.seat.seat_type,
                'price': float(ss.price),
                'status': seat_status
            })

        reservation_info = None
        if user_reservation and user_reservation.is_active():
            rem_sec = max(0, int((user_reservation.expires_at - now).total_seconds()))
            reservation_info = {
                'reservation_token': user_reservation.reservation_token,
                'expires_at': user_reservation.expires_at.isoformat(),
                'remaining_seconds': rem_sec,
                'total_amount': float(user_reservation.total_amount)
            }

        return JsonResponse({
            'success': True,
            'show_id': show.id,
            'movie_title': show.movie.title,
            'theater_name': show.screen.theater.name,
            'city_name': show.screen.theater.city.name,
            'screen_name': show.screen.name,
            'base_price': float(show.base_price),
            'reservation': reservation_info,
            'seats': seats_data
        })


@method_decorator(csrf_exempt, name='dispatch')
class ReserveSeatsAPIView(View):
    """
    POST /api/shows/<show_id>/seats/reserve/
    Atomically reserves selected seats for EXACTLY 2 MINUTES.
    Prevents concurrent double-booking using select_for_update().
    """
    def post(self, request, show_id):
        import json
        show = get_object_or_404(Show, pk=show_id)

        # Parse JSON or POST payload
        try:
            if request.content_type == 'application/json':
                body = json.loads(request.body)
                seat_ids = body.get('seat_ids', [])
            else:
                seat_ids = request.POST.getlist('seat_ids')
                if not seat_ids and request.POST.get('seat_ids'):
                    seat_ids = [s.strip() for s in request.POST.get('seat_ids').split(',')]
        except Exception:
            return JsonResponse({'success': False, 'code': 'BAD_REQUEST', 'message': 'Invalid payload format.'}, status=400)

        # Convert to integers
        try:
            seat_ids = [int(sid) for sid in seat_ids if sid]
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'code': 'INVALID_SEATS', 'message': 'Seat IDs must be valid integers.'}, status=400)

        if not seat_ids:
            return JsonResponse({'success': False, 'code': 'NO_SEATS_SELECTED', 'message': 'Please select at least one seat.'}, status=400)

        if len(seat_ids) > 10:
            return JsonResponse({'success': False, 'code': 'MAX_LIMIT_EXCEEDED', 'message': 'Maximum 10 seats allowed per transaction.'}, status=400)

        lazy_clean_expired_reservations(show=show)
        now = timezone.now()
        expires_at = now + timedelta(minutes=2)
        reservation_token = f"RES-{uuid.uuid4().hex.upper()}"

        # ----------------------------------------------------
        # Atomic Concurrency Protection with DB Lock
        # ----------------------------------------------------
        try:
            with transaction.atomic():
                from django.db import connection
                qs = ShowSeat.objects.filter(show=show)
                if connection.vendor != 'sqlite':
                    qs = qs.select_for_update()

                target_show_seats = list(
                    qs.filter(seat_id__in=seat_ids).select_related('seat')
                )

                if len(target_show_seats) != len(seat_ids):
                    # Try matching by ShowSeat primary key ID if passed
                    qs2 = ShowSeat.objects.filter(show=show)
                    if connection.vendor != 'sqlite':
                        qs2 = qs2.select_for_update()
                    target_show_seats = list(
                        qs2.filter(id__in=seat_ids).select_related('seat')
                    )

                if len(target_show_seats) != len(seat_ids):
                    return JsonResponse({
                        'success': False,
                        'code': 'SEAT_NOT_FOUND',
                        'message': 'One or more requested seats could not be found.'
                    }, status=404)

                current_user = request.user if request.user.is_authenticated else None

                # Check if any seat is already booked or actively reserved by someone else
                unavailable_seats = []
                for ss in target_show_seats:
                    if ss.status == 'BOOKED':
                        unavailable_seats.append(f"{ss.seat.row}{ss.seat.number}")
                    elif ss.status == 'RESERVED' and ss.reservation:
                        if ss.reservation.is_active():
                            if current_user is None or ss.reservation.user_id != current_user.id:
                                unavailable_seats.append(f"{ss.seat.row}{ss.seat.number}")

                if unavailable_seats:
                    return JsonResponse({
                        'success': False,
                        'code': 'SEAT_UNAVAILABLE',
                        'message': f"Seats {', '.join(unavailable_seats)} are no longer available.",
                        'unavailable_seats': unavailable_seats
                    }, status=409)

                # Cancel any previous active reservation held by this user for this show
                if current_user:
                    old_user_res = SeatReservation.objects.filter(
                        show=show,
                        user=current_user,
                        status__in=['ACTIVE', 'RESERVED']
                    )
                    old_res_ids = list(old_user_res.values_list('id', flat=True))
                    if old_res_ids:
                        ShowSeat.objects.filter(reservation_id__in=old_res_ids).update(status='AVAILABLE', reservation=None)
                        old_user_res.update(status='CANCELLED')

                # Create Master Reservation
                total_amount = sum(ss.price for ss in target_show_seats)

                primary_seat = target_show_seats[0].seat
                master_reservation = SeatReservation.objects.create(
                    show=show,
                    seat=primary_seat,
                    user=current_user,
                    reservation_token=reservation_token,
                    status='ACTIVE',
                    total_amount=total_amount,
                    expires_at=expires_at
                )

                # Link all selected ShowSeats to the Master Reservation
                seat_labels = []
                for ss in target_show_seats:
                    ss.status = 'RESERVED'
                    ss.reservation = master_reservation
                    ss.save(update_fields=['status', 'reservation'])
                    seat_labels.append(f"{ss.seat.row}{ss.seat.number}")

            # Broadcast WebSocket seat state update
            from .consumers import broadcast_seat_status_change
            broadcast_seat_status_change(show.id, seat_labels, 'RESERVED', expires_at.isoformat())

        except Exception as e:
            logger.error(f"Error during seat reservation: {e}")
            return JsonResponse({
                'success': False,
                'code': 'SERVER_ERROR',
                'message': 'Failed to process seat reservation due to a database error.'
            }, status=500)

        return JsonResponse({
            'success': True,
            'reservation_token': reservation_token,
            'expires_at': expires_at.isoformat(),
            'remaining_seconds': 120,
            'seats': seat_labels,
            'total_amount': float(total_amount),
            'message': 'Seats reserved for 2 minutes.'
        })


class ReservationDetailAPIView(LoginRequiredMixin, View):
    """
    GET /api/reservations/<reservation_token>/
    DELETE /api/reservations/<reservation_token>/
    """
    def get(self, request, reservation_token):
        reservation = get_object_or_404(SeatReservation, reservation_token=reservation_token, user=request.user)

        now = timezone.now()
        is_expired = (reservation.expires_at <= now or reservation.status == 'EXPIRED')

        if is_expired and reservation.status in ['ACTIVE', 'RESERVED']:
            with transaction.atomic():
                ShowSeat.objects.filter(reservation=reservation).update(status='AVAILABLE', reservation=None)
                reservation.status = 'EXPIRED'
                reservation.save(update_fields=['status'])

        rem_sec = max(0, int((reservation.expires_at - now).total_seconds())) if not is_expired else 0
        show_seats = ShowSeat.objects.filter(reservation=reservation).select_related('seat')
        seat_labels = [f"{ss.seat.row}{ss.seat.number}" for ss in show_seats]

        return JsonResponse({
            'success': True,
            'reservation_token': reservation.reservation_token,
            'show_id': reservation.show_id,
            'status': reservation.status,
            'is_active': reservation.is_active(),
            'expires_at': reservation.expires_at.isoformat(),
            'remaining_seconds': rem_sec,
            'seats': seat_labels,
            'total_amount': float(reservation.total_amount)
        })

    def delete(self, request, reservation_token):
        reservation = get_object_or_404(SeatReservation, reservation_token=reservation_token, user=request.user)

        with transaction.atomic():
            show_seats = list(ShowSeat.objects.filter(reservation=reservation).select_related('seat'))
            seat_labels = [f"{ss.seat.row}{ss.seat.number}" for ss in show_seats]

            ShowSeat.objects.filter(reservation=reservation).update(status='AVAILABLE', reservation=None)
            reservation.status = 'CANCELLED'
            reservation.save(update_fields=['status'])

            from .consumers import broadcast_seat_status_change
            broadcast_seat_status_change(reservation.show_id, seat_labels, 'AVAILABLE')

        return JsonResponse({
            'success': True,
            'message': 'Reservation cancelled and seats released.'
        })
