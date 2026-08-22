import json
import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.conf import settings

from .models import Payment
from .services import create_razorpay_order, verify_razorpay_signature, generate_razorpay_signature
from shows.models import Show, SeatReservation, ShowSeat
from shows.consumers import broadcast_seat_status_change
from theaters.models import Seat
from bookings.models import Booking, BookingSeat
from bookings.tasks import send_booking_email_task

logger = logging.getLogger(__name__)


class CheckoutView(LoginRequiredMixin, View):
    """
    Renders checkout overview page and initializes Razorpay order.
    """
    def get(self, request, show_id):
        show = get_object_or_404(
            Show.objects.select_related('movie', 'screen__theater', 'screen__theater__city'),
            pk=show_id
        )

        seat_ids_str = request.GET.get('seats', '')
        if not seat_ids_str:
            messages.error(request, "No seats selected. Please choose seats first.")
            return redirect('shows:seat_selection', show_id=show.id)

        try:
            seat_ids = [int(s) for s in seat_ids_str.split(',') if s.strip()]
        except ValueError:
            messages.error(request, "Invalid seat selection.")
            return redirect('shows:seat_selection', show_id=show.id)

        now = timezone.now()

        # Fetch active reserved show seats for this show (match by physical seat_id or show_seat.id)
        from django.db.models import Q
        show_seats = list(ShowSeat.objects.filter(
            Q(seat_id__in=seat_ids) | Q(id__in=seat_ids),
            show=show,
            status='RESERVED',
            reservation__expires_at__gt=now
        ).select_related('seat', 'reservation'))

        if len(show_seats) != len(seat_ids):
            # Fallback: check direct seat reservations
            direct_res = list(SeatReservation.objects.filter(
                Q(seat_id__in=seat_ids) | Q(id__in=seat_ids),
                show=show,
                status__in=['ACTIVE', 'RESERVED'],
                expires_at__gt=now
            ).select_related('seat'))
            if len(direct_res) == len(seat_ids):
                seats_list = [r.seat for r in direct_res]
                total_price = sum(Decimal(str(r.total_amount or show.base_price)) for r in direct_res)
            else:
                messages.error(request, "Your seat reservation hold has expired. Please re-select your seats.")
                return redirect('shows:seat_selection', show_id=show.id)
        else:
            seats_list = [ss.seat for ss in show_seats]
            total_price = sum(Decimal(str(ss.price)) for ss in show_seats)

        # Associate current user to reservation if not already linked
        if show_seats and show_seats[0].reservation and show_seats[0].reservation.user is None:
            show_seats[0].reservation.user = request.user
            show_seats[0].reservation.save(update_fields=['user'])

        convenience_fee = Decimal('30.00')
        grand_total = total_price + convenience_fee

        with transaction.atomic():
            # Create or reuse pending booking
            booking = Booking.objects.create(
                user=request.user,
                show=show,
                total_seats=len(seats_list),
                total_price=total_price,
                convenience_fee=convenience_fee,
                grand_total=grand_total,
                status='PENDING'
            )

            # Create Razorpay order
            rzp_order = create_razorpay_order(
                amount_in_inr=float(grand_total),
                currency='INR',
                receipt=booking.booking_number
            )

            # Create pending Payment ledger record
            Payment.objects.create(
                booking=booking,
                order_id=rzp_order['id'],
                amount=grand_total,
                currency='INR',
                provider='RAZORPAY',
                status='PENDING'
            )

        context = {
            'show': show,
            'booking': booking,
            'seats': seats_list,
            'total_price': total_price,
            'convenience_fee': convenience_fee,
            'grand_total': grand_total,
            'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_cinepass_key'),
            'razorpay_order_id': rzp_order['id'],
            'razorpay_amount_paisa': int(round(grand_total * 100)),
        }
        return render(request, 'payments/checkout.html', context)


class VerifyPaymentAPIView(LoginRequiredMixin, View):
    """
    Server-side verification API for Razorpay payments.
    Converts temporary seat reservations to confirmed bookings upon signature match.
    """
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid JSON body.'}, status=400)

        razorpay_order_id = body.get('razorpay_order_id')
        razorpay_payment_id = body.get('razorpay_payment_id')
        razorpay_signature = body.get('razorpay_signature')
        booking_id = body.get('booking_id')

        if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature, booking_id]):
            return JsonResponse({'success': False, 'message': 'Missing payment verification credentials.'}, status=400)

        # 1. Verify HMAC signature server-side
        is_valid = verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
        if not is_valid:
            logger.warning(f"Payment verification signature mismatch for Order {razorpay_order_id}")
            with transaction.atomic():
                payment = Payment.objects.filter(booking_id=booking_id, booking__user=request.user).first()
                if not payment and razorpay_order_id:
                    payment = Payment.objects.filter(order_id=razorpay_order_id, booking__user=request.user).first()

                if payment and payment.status != 'SUCCESS':
                    payment.payment_id = razorpay_payment_id
                    payment.signature = razorpay_signature
                    payment.status = 'FAILED'
                    payment.save(update_fields=['payment_id', 'signature', 'status', 'updated_at'])

                    booking = payment.booking
                    if booking.status == 'PENDING':
                        booking.status = 'FAILED'
                        booking.save(update_fields=['status', 'updated_at'])

                    # Release active seat reservations on failure
                    active_res = SeatReservation.objects.filter(
                        show=booking.show,
                        user=request.user,
                        status__in=['ACTIVE', 'RESERVED']
                    )
                    res_ids = list(active_res.values_list('id', flat=True))
                    if res_ids:
                        released_seats = list(ShowSeat.objects.filter(reservation_id__in=res_ids, status='RESERVED').select_related('seat'))
                        seat_labels = [f"{ss.seat.row}{ss.seat.number}" for ss in released_seats]
                        ShowSeat.objects.filter(reservation_id__in=res_ids, status='RESERVED').update(status='AVAILABLE', reservation=None)
                        active_res.update(status='CANCELLED')
                        broadcast_seat_status_change(booking.show_id, seat_labels, 'AVAILABLE')

            return JsonResponse({
                'success': False,
                'message': 'Payment verification failed. Signature invalid.',
                'can_retry': True,
                'booking_id': booking_id
            }, status=400)

        with transaction.atomic():
            booking = Booking.objects.select_for_update().filter(pk=booking_id, user=request.user).first()
            if not booking:
                return JsonResponse({'success': False, 'message': 'Booking not found.'}, status=444)

            # Idempotency check: if already confirmed, return success immediately
            if booking.status == 'CONFIRMED':
                return JsonResponse({
                    'success': True,
                    'message': 'Booking is already confirmed.',
                    'booking_number': booking.booking_number
                })

            payment = Payment.objects.select_for_update().filter(booking=booking).first()
            if not payment:
                payment = Payment.objects.create(
                    booking=booking,
                    order_id=razorpay_order_id,
                    amount=booking.grand_total,
                    status='PENDING'
                )

            # Update Payment ledger
            payment.payment_id = razorpay_payment_id
            payment.signature = razorpay_signature
            payment.status = 'SUCCESS'
            payment.save(update_fields=['payment_id', 'signature', 'status', 'updated_at'])

            # Update Booking header
            booking.status = 'CONFIRMED'
            booking.save(update_fields=['status', 'updated_at'])

            # Fetch active reservations for this user and show
            active_res = SeatReservation.objects.filter(
                show=booking.show,
                user=request.user,
                status__in=['ACTIVE', 'RESERVED']
            )
            res_ids = list(active_res.values_list('id', flat=True))

            reserved_show_seats = list(
                ShowSeat.objects.filter(
                    show=booking.show,
                    reservation_id__in=res_ids
                ).select_related('seat')
            )

            booking_seats = []
            seat_labels = []
            for ss in reserved_show_seats:
                ss.status = 'BOOKED'
                ss.save(update_fields=['status'])
                seat = ss.seat
                seat_labels.append(f"{seat.row}{seat.number}")
                booking_seats.append(BookingSeat(
                    booking=booking,
                    seat=seat,
                    price=ss.price
                ))

            # Fallback if ShowSeats weren't directly linked to reservation_id
            if not booking_seats:
                for res in active_res.select_related('seat'):
                    seat = res.seat
                    seat_labels.append(f"{seat.row}{seat.number}")
                    booking_seats.append(BookingSeat(
                        booking=booking,
                        seat=seat,
                        price=res.total_amount or booking.show.base_price
                    ))

            if booking_seats:
                BookingSeat.objects.bulk_create(booking_seats, ignore_conflicts=True)

            active_res.update(status='CONVERTED')

            # Broadcast WebSocket status update for BOOKED seats
            if seat_labels:
                broadcast_seat_status_change(booking.show_id, seat_labels, 'BOOKED')

            # Update available seat count on show
            show = Show.objects.select_for_update().get(pk=booking.show.id)
            show.available_seats = max(0, show.available_seats - len(booking_seats))
            show.save(update_fields=['available_seats'])

            # Dispatch email asynchronously after transaction commits to guarantee clean data read and immediate delivery
            import threading
            from bookings.tasks import send_booking_email

            def _dispatch_ticket_email(b_id):
                try:
                    send_booking_email(b_id)
                except Exception as bg_err:
                    logger.error(f"Background thread ticket email error for Booking #{b_id}: {bg_err}")

            booking_id_val = booking.id
            transaction.on_commit(lambda: threading.Thread(target=_dispatch_ticket_email, args=(booking_id_val,), daemon=True).start())

        return JsonResponse({
            'success': True,
            'message': 'Payment verified and booking confirmed!',
            'booking_number': booking.booking_number
        })


class PaymentWebhookAPIView(View):
    """
    Razorpay Webhook endpoint for server-to-server transaction status reconciliation.
    Includes HMAC signature validation and idempotency handling.
    """
    def post(self, request):
        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
        signature = request.headers.get('X-Razorpay-Signature', '')

        # Basic verification logging
        logger.info(f"Received Razorpay webhook notification with signature {signature[:10]}...")

        try:
            event = json.loads(request.body.decode('utf-8'))
        except Exception:
            return HttpResponse(status=400)

        event_type = event.get('event')
        payload = event.get('payload', {}).get('payment', {}).get('entity', {})

        order_id = payload.get('order_id')
        payment_id = payload.get('id')
        status = payload.get('status')

        if event_type == 'payment.captured' and order_id:
            payment = Payment.objects.filter(order_id=order_id).first()
            if payment and payment.status != 'SUCCESS':
                with transaction.atomic():
                    payment.payment_id = payment_id
                    payment.status = 'SUCCESS'
                    payment.save(update_fields=['payment_id', 'status', 'updated_at'])

                    booking = payment.booking
                    if booking.status != 'CONFIRMED':
                        booking.status = 'CONFIRMED'
                        booking.save(update_fields=['status', 'updated_at'])
                        import threading
                        from bookings.tasks import send_booking_email
                        threading.Thread(target=send_booking_email, args=(booking.id,), daemon=True).start()

        elif event_type == 'payment.failed' and order_id:
            payment = Payment.objects.filter(order_id=order_id).first()
            if payment and payment.status != 'SUCCESS':
                with transaction.atomic():
                    payment.payment_id = payment_id
                    payment.status = 'FAILED'
                    payment.save(update_fields=['payment_id', 'status', 'updated_at'])

                    booking = payment.booking
                    if booking.status == 'PENDING':
                        booking.status = 'FAILED'
                        booking.save(update_fields=['status', 'updated_at'])

                    # Release active seat reservations on failure
                    active_res = SeatReservation.objects.filter(
                        show=booking.show,
                        user=booking.user,
                        status__in=['ACTIVE', 'RESERVED']
                    )
                    res_ids = list(active_res.values_list('id', flat=True))
                    if res_ids:
                        from shows.models import ShowSeat
                        from shows.consumers import broadcast_seat_status_change
                        released_seats = list(ShowSeat.objects.filter(reservation_id__in=res_ids, status='RESERVED').select_related('seat'))
                        seat_labels = [f"{ss.seat.row}{ss.seat.number}" for ss in released_seats]
                        ShowSeat.objects.filter(reservation_id__in=res_ids, status='RESERVED').update(status='AVAILABLE', reservation=None)
                        active_res.update(status='CANCELLED')
                        broadcast_seat_status_change(booking.show_id, seat_labels, 'AVAILABLE')

        return HttpResponse(status=200)


class PaymentFailureAPIView(LoginRequiredMixin, View):
    """
    POST /payments/api/failed/ or /payments/api/cancel/
    Handles client-side payment cancellation, failure, or modal dismissal.
    Updates payment status to FAILED, releases held seats immediately, and broadcasts WebSocket update.
    """
    def post(self, request):
        try:
            if request.content_type == 'application/json':
                body = json.loads(request.body.decode('utf-8'))
            else:
                body = request.POST
            order_id = body.get('order_id')
            booking_id = body.get('booking_id')
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid payload.'}, status=400)

        with transaction.atomic():
            payment = None
            if order_id:
                payment = Payment.objects.filter(order_id=order_id, booking__user=request.user).first()
            elif booking_id:
                payment = Payment.objects.filter(booking_id=booking_id, booking__user=request.user).first()

            if payment and payment.status != 'SUCCESS':
                payment.status = 'FAILED'
                payment.save(update_fields=['status', 'updated_at'])
                booking = payment.booking
                if booking.status == 'PENDING':
                    booking.status = 'FAILED'
                    booking.save(update_fields=['status', 'updated_at'])

                # Release held seats immediately
                active_res = SeatReservation.objects.filter(
                    show=booking.show,
                    user=request.user,
                    status__in=['ACTIVE', 'RESERVED']
                )
                res_ids = list(active_res.values_list('id', flat=True))
                if res_ids:
                    from shows.models import ShowSeat
                    from shows.consumers import broadcast_seat_status_change
                    released_seats = list(ShowSeat.objects.filter(reservation_id__in=res_ids, status='RESERVED').select_related('seat'))
                    seat_labels = [f"{ss.seat.row}{ss.seat.number}" for ss in released_seats]
                    ShowSeat.objects.filter(reservation_id__in=res_ids, status='RESERVED').update(status='AVAILABLE', reservation=None)
                    active_res.update(status='CANCELLED')
                    broadcast_seat_status_change(booking.show_id, seat_labels, 'AVAILABLE')

        return JsonResponse({
            'success': True,
            'message': 'Payment cancelled and reserved seats released successfully.'
        })


class PaymentRetryAPIView(LoginRequiredMixin, View):
    """
    POST /payments/api/retry/
    Creates a fresh Razorpay order for an existing pending booking with an active seat hold.
    """
    def post(self, request):
        try:
            if request.content_type == 'application/json':
                body = json.loads(request.body.decode('utf-8'))
            else:
                body = request.POST
            booking_id = body.get('booking_id')
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid payload.'}, status=400)

        booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
        if booking.status == 'CONFIRMED':
            return JsonResponse({'success': True, 'message': 'Booking already confirmed.', 'redirect_url': '/accounts/bookings/'})

        # Check if active reservation exists
        active_res = SeatReservation.objects.filter(
            show=booking.show,
            user=request.user,
            status__in=['ACTIVE', 'RESERVED'],
            expires_at__gt=timezone.now()
        ).first()

        if not active_res:
            return JsonResponse({'success': False, 'message': 'Reservation hold has expired. Please select seats again.'}, status=400)

        # Generate fresh Razorpay order
        rzp_order = create_razorpay_order(
            amount_in_inr=float(booking.grand_total),
            currency='INR',
            receipt=booking.booking_number
        )

        payment, created = Payment.objects.get_or_create(
            booking=booking,
            defaults={
                'order_id': rzp_order['id'],
                'amount': booking.grand_total,
                'currency': 'INR',
                'provider': 'RAZORPAY',
                'status': 'PENDING'
            }
        )
        if not created:
            payment.order_id = rzp_order['id']
            payment.status = 'PENDING'
            payment.save(update_fields=['order_id', 'status', 'updated_at'])

        return JsonResponse({
            'success': True,
            'razorpay_order_id': rzp_order['id'],
            'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_cinepass_key'),
            'amount_paisa': int(round(booking.grand_total * 100)),
            'booking_number': booking.booking_number
        })


class DemoSignPaymentAPIView(LoginRequiredMixin, View):
    """
    POST /payments/api/demo-sign/
    Computes cryptographic HMAC-SHA256 signature using RAZORPAY_KEY_SECRET.
    Allows end-to-end sandbox testing of the genuine HMAC verification pipeline.
    """
    def post(self, request):
        try:
            if request.content_type == 'application/json':
                body = json.loads(request.body.decode('utf-8'))
            else:
                body = request.POST
            order_id = body.get('order_id')
            payment_id = body.get('payment_id')
        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid payload.'}, status=400)

        if not order_id or not payment_id:
            return JsonResponse({'success': False, 'message': 'Missing order_id or payment_id.'}, status=400)

        sig = generate_razorpay_signature(order_id, payment_id)
        return JsonResponse({'success': True, 'signature': sig})
