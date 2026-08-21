from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from .models import Show, SeatReservation
from theaters.models import Seat
from bookings.models import BookingSeat, Booking

from .api_views import ensure_show_seats_initialized, lazy_clean_expired_reservations

class ShowSeatSelectionView(View):
    """
    Renders the interactive cinema seat map interface for a given show.
    """
    def get(self, request, show_id):
        show = get_object_or_404(
            Show.objects.select_related('movie', 'screen__theater', 'screen__theater__city'),
            pk=show_id
        )

        # Lazy cleanup of stale reservations and ensure seats initialized
        lazy_clean_expired_reservations(show=show)
        ensure_show_seats_initialized(show)

        return render(request, 'shows/seat_selection.html', {
            'show': show,
            'screen': show.screen,
            'theater': show.screen.theater,
            'movie': show.movie,
        })


class ShowSeatMatrixAPIView(View):
    """
    API returning current real-time seat states (AVAILABLE, TEMPORARILY_RESERVED, BOOKED)
    for seat grid UI rendering.
    """
    def get(self, request, show_id):
        show = get_object_or_404(Show.objects.select_related('screen'), pk=show_id)

        # Auto-expire outdated reservations
        now = timezone.now()
        SeatReservation.objects.filter(
            show=show,
            status='RESERVED',
            expires_at__lte=now
        ).update(status='EXPIRED')

        # Get booked seat IDs (confirmed or active pending bookings)
        booked_seat_ids = set(
            BookingSeat.objects.filter(
                booking__show=show,
                booking__status__in=['CONFIRMED', 'PENDING']
            ).values_list('seat_id', flat=True)
        )

        # Get active temporarily reserved seat IDs
        session_key = request.session.session_key or ''
        active_reservations = SeatReservation.objects.filter(
            show=show,
            status='RESERVED',
            expires_at__gt=now
        ).select_related('seat')

        reserved_seat_ids = set()
        user_reserved_seat_ids = set()

        for res in active_reservations:
            reserved_seat_ids.add(res.seat_id)
            if (request.user.is_authenticated and res.user == request.user) or (res.session_key and res.session_key == session_key):
                user_reserved_seat_ids.add(res.seat_id)

        # Fetch all seats for the screen
        seats = Seat.objects.filter(screen=show.screen, is_active=True).order_by('row', 'number')

        seat_matrix = []
        for seat in seats:
            status = 'AVAILABLE'
            if seat.id in booked_seat_ids:
                status = 'BOOKED'
            elif seat.id in user_reserved_seat_ids:
                status = 'SELECTED'
            elif seat.id in reserved_seat_ids:
                status = 'TEMPORARILY_RESERVED'

            # Tier pricing calculation
            seat_price = show.base_price
            if seat.seat_type == 'PREMIUM':
                seat_price *= Decimal('1.25')
            elif seat.seat_type in ['VIP', 'RECLINER']:
                seat_price *= Decimal('1.50')

            seat_matrix.append({
                'id': seat.id,
                'row': seat.row,
                'number': seat.number,
                'seat_type': seat.seat_type,
                'price': float(round(seat_price, 2)),
                'status': status
            })

        return JsonResponse({
            'success': True,
            'show_id': show.id,
            'movie_title': show.movie.title,
            'screen_name': show.screen.name,
            'base_price': float(show.base_price),
            'seats': seat_matrix
        })


class ReserveSeatsAPIView(LoginRequiredMixin, View):
    """
    Atomic seat reservation API enforcing 2-minute row-level concurrency lock.
    """
    def post(self, request, show_id):
        import json
        try:
            body = json.loads(request.body.decode('utf-8'))
            seat_ids = body.get('seat_ids', [])
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid JSON request payload.', 'code': 'INVALID_PAYLOAD'}, status=400)

        if not seat_ids:
            return JsonResponse({'success': False, 'message': 'No seats selected for reservation.', 'code': 'NO_SEATS'}, status=400)

        now = timezone.now()
        expires_at = now + timedelta(minutes=2)
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key

        with transaction.atomic():
            show = get_object_or_404(Show.objects.select_for_update(), pk=show_id)

            # Clean expired reservations
            SeatReservation.objects.filter(
                show=show,
                status='RESERVED',
                expires_at__lte=now
            ).update(status='EXPIRED')

            # Verify no selected seats are already booked
            already_booked = BookingSeat.objects.filter(
                booking__show=show,
                booking__status__in=['CONFIRMED', 'PENDING'],
                seat_id__in=seat_ids
            ).exists()

            if already_booked:
                return JsonResponse({
                    'success': False,
                    'message': 'One or more selected seats have already been booked.',
                    'code': 'SEAT_UNAVAILABLE'
                }, status=409)

            # Verify no selected seats are active reserved by another user
            active_conflicts = SeatReservation.objects.filter(
                show=show,
                seat_id__in=seat_ids,
                status='RESERVED',
                expires_at__gt=now
            ).exclude(user=request.user)

            if active_conflicts.exists():
                return JsonResponse({
                    'success': False,
                    'message': 'One or more selected seats are currently reserved by another customer.',
                    'code': 'SEAT_LOCKED'
                }, status=409)

            # Cancel previous active reservations for this user on this show to refresh selection
            SeatReservation.objects.filter(
                show=show,
                user=request.user,
                status='RESERVED'
            ).update(status='EXPIRED')

            # Create new 2-minute atomic reservations
            new_reservations = []
            seats = Seat.objects.filter(id__in=seat_ids, screen=show.screen)
            if seats.count() != len(seat_ids):
                return JsonResponse({'success': False, 'message': 'One or more seat IDs are invalid.', 'code': 'INVALID_SEATS'}, status=400)

            total_price = Decimal('0.00')
            for seat in seats:
                new_reservations.append(SeatReservation(
                    show=show,
                    seat=seat,
                    user=request.user,
                    session_key=session_key,
                    status='RESERVED',
                    expires_at=expires_at
                ))
                seat_price = show.base_price
                if seat.seat_type == 'PREMIUM':
                    seat_price *= Decimal('1.25')
                elif seat.seat_type in ['VIP', 'RECLINER']:
                    seat_price *= Decimal('1.50')
                total_price += seat_price

            SeatReservation.objects.bulk_create(new_reservations)

        convenience_fee = Decimal('30.00')
        grand_total = total_price + convenience_fee

        return JsonResponse({
            'success': True,
            'message': 'Seats successfully reserved for 2 minutes.',
            'expires_at': expires_at.isoformat(),
            'countdown_seconds': 120,
            'show_id': show.id,
            'seat_count': len(seat_ids),
            'total_price': float(round(total_price, 2)),
            'convenience_fee': float(convenience_fee),
            'grand_total': float(round(grand_total, 2))
        })
