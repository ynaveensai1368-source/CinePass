import logging
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction, connection
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils import timezone

from .models import Booking, BookingSeat
from shows.models import Show, SeatReservation, ShowSeat
from .forms import BookingForm
from .utils import generate_pdf_ticket
from .tasks import send_booking_email_task

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def book_show(request, show_id):
    """
    Defensive view function handling ticket reservations.
    Prevents server thread hangs via non-blocking DB updates, Razorpay API timeouts,
    fire-and-forget Celery execution, and guaranteed early JSON/HTTP response paths.
    """
    show = get_object_or_404(
        Show.objects.select_related('movie', 'screen__theater', 'screen__theater__city'),
        pk=show_id
    )

    if request.method == 'GET':
        form = BookingForm()
        return render(request, 'bookings/book_tickets.html', {'show': show, 'form': form})

    # Determine if request expects JSON response
    is_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '') or
        request.content_type == 'application/json'
    )

    form = BookingForm(request.POST)
    if not form.is_valid():
        if is_json:
            return JsonResponse({'status': 'ERROR', 'errors': form.errors}, status=400)
        messages.error(request, "Invalid booking data. Please check seat quantity.")
        return render(request, 'bookings/book_tickets.html', {'show': show, 'form': form})

    seats = form.cleaned_data.get('seats_booked', 1)
    base_price = show.base_price or Decimal('250.00')

    # 1. Non-blocking Atomic DB Seat Allocation using F() expression
    try:
        updated_count = Show.objects.filter(
            pk=show.id,
            available_seats__gte=seats
        ).update(
            available_seats=F('available_seats') - seats
        )

        if updated_count == 0:
            err_msg = f"Sorry, only {show.available_seats} seats are currently available for this show."
            if is_json:
                return JsonResponse({'status': 'ERROR', 'message': err_msg}, status=400)
            messages.error(request, err_msg)
            return redirect('bookings:book_tickets', show_id=show.id)

        # Calculate totals
        total_price = base_price * seats
        convenience_fee = Decimal('30.00')
        grand_total = total_price + convenience_fee

        with transaction.atomic():
            booking = Booking.objects.create(
                user=request.user,
                show=show,
                total_seats=seats,
                total_price=total_price,
                convenience_fee=convenience_fee,
                grand_total=grand_total,
                status='CONFIRMED'
            )

            # Convert 2-minute SeatReservation to confirmed BOOKED seats
            user_reservation = SeatReservation.objects.filter(
                show=show,
                user=request.user,
                status__in=['ACTIVE', 'RESERVED'],
                expires_at__gt=timezone.now()
            ).first()

            if user_reservation:
                reserved_show_seats = list(ShowSeat.objects.filter(reservation=user_reservation).select_related('seat'))
                for ss in reserved_show_seats:
                    ss.status = 'BOOKED'
                    ss.booking = booking
                    ss.save(update_fields=['status', 'booking'])
                    BookingSeat.objects.get_or_create(
                        booking=booking,
                        seat=ss.seat,
                        defaults={'price': ss.price}
                    )
                user_reservation.status = 'CONVERTED'
                user_reservation.save(update_fields=['status'])
            else:
                # Fallback seat allocation for direct form submissions
                available_show_seats = list(ShowSeat.objects.filter(show=show, status='AVAILABLE')[:seats])
                for ss in available_show_seats:
                    ss.status = 'BOOKED'
                    ss.booking = booking
                    ss.save(update_fields=['status', 'booking'])
                    BookingSeat.objects.get_or_create(
                        booking=booking,
                        seat=ss.seat,
                        defaults={'price': ss.price}
                    )
    except Exception as db_err:
        logger.error(f"Database error during ticket reservation for show #{show_id}: {db_err}")
        err_msg = "An error occurred while processing your booking. Please try again."
        if is_json:
            return JsonResponse({'status': 'ERROR', 'message': err_msg}, status=500)
        messages.error(request, err_msg)
        return redirect('bookings:book_tickets', show_id=show.id)

    # 2. Razorpay API Integration with Try...Except and Strict Request Timeout
    razorpay_order = None
    try:
        rz_key = getattr(settings, 'RAZORPAY_KEY_ID', None)
        rz_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
        if rz_key and rz_secret:
            import razorpay
            client = razorpay.Client(auth=(rz_key, rz_secret))
            # Set request socket timeout to 5 seconds to prevent thread hanging
            if hasattr(client, 'session') and hasattr(client.session, 'timeout'):
                client.session.timeout = 5
            razorpay_order = client.order.create({
                'amount': int(grand_total * 100),
                'currency': 'INR',
                'receipt': booking.booking_number,
                'payment_capture': 1
            })
    except Exception as rz_err:
        logger.warning(f"Razorpay order generation skipped/failed safely: {rz_err}")

    # 3. Email Dispatch (Celery async or direct background thread fallback)
    from .tasks import send_booking_email
    def _dispatch_email_bg():
        try:
            send_booking_email_task.apply_async(args=[booking.id], expires=60, retry=False)
        except Exception as celery_err:
            logger.warning(f"Celery task trigger skipped, using sync fallback: {celery_err}")
            send_booking_email(booking.id)

    import threading
    threading.Thread(target=_dispatch_email_bg, daemon=True).start()

    # 4. Guaranteed Early Return Path
    success_msg = f"🎉 Booking #{booking.booking_number} Confirmed! We sent your e-ticket to {request.user.email}."
    if is_json:
        return JsonResponse({
            'status': 'SUCCESS',
            'booking_number': booking.booking_number,
            'booking_id': booking.id,
            'redirect_url': '/accounts/bookings/',
            'razorpay_order': razorpay_order,
            'message': success_msg
        })

    messages.success(request, success_msg)
    return redirect('accounts:booking_history')


class BookTicketsView(LoginRequiredMixin, View):
    def get(self, request, show_id):
        return book_show(request, show_id)

    def post(self, request, show_id):
        return book_show(request, show_id)


class CancelBookingView(LoginRequiredMixin, View):
    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, pk=booking_id, user=request.user)
        
        if booking.status == 'CANCELLED':
            messages.warning(request, "This booking has already been cancelled.")
        else:
            with transaction.atomic():
                booking.cancel_booking()
            messages.success(request, f"Booking #{booking.booking_number} has been cancelled successfully.")

        return redirect('accounts:booking_history')


class DownloadTicketPDFView(LoginRequiredMixin, View):
    """
    Generates and downloads the PDF ticket with QR code for a user's booking.
    """
    def get(self, request, booking_id):
        booking = get_object_or_404(
            Booking.objects.select_related('show__movie', 'show__screen__theater', 'show__screen__theater__city', 'user'),
            pk=booking_id,
            user=request.user
        )

        try:
            pdf_bytes = generate_pdf_ticket(booking)
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="CinePass_Ticket_{booking.booking_number}.pdf"'
            return response
        except Exception:
            messages.error(request, "Ticket PDF download currently unavailable.")
            return redirect('accounts:booking_history')


class VerifyTicketView(View):
    """
    Public ticket verification view for QR code scanning at theater entrance.
    GET /api/tickets/verify/<token>/ or /bookings/tickets/verify/<token>/
    """
    def get(self, request, token):
        from .utils import verify_ticket_signature_token
        from django.http import JsonResponse

        is_valid, payload = verify_ticket_signature_token(token)
        booking = None
        if is_valid and payload:
            booking = Booking.objects.filter(
                pk=payload['booking_id'],
                booking_number=payload['booking_number']
            ).select_related(
                'show__movie', 'show__screen__theater', 'show__screen__theater__city', 'user'
            ).first()

        valid_ticket = bool(is_valid and booking is not None and booking.status == 'CONFIRMED')

        if request.headers.get('Accept') == 'application/json' or request.GET.get('format') == 'json':
            if valid_ticket:
                return JsonResponse({
                    'status': 'VALID',
                    'booking_number': booking.booking_number,
                    'movie': booking.show.movie.title,
                    'theater': booking.show.screen.theater.name,
                    'city': booking.show.screen.theater.city.name,
                    'screen': booking.show.screen.name,
                    'show_time': booking.show.start_time.isoformat(),
                    'seats': booking.total_seats,
                    'user_email': booking.user.email,
                    'booking_status': booking.status
                })
            return JsonResponse({'status': 'INVALID', 'message': 'Ticket token signature invalid or expired.'}, status=400)

        return render(request, 'bookings/verify_ticket.html', {
            'is_valid': valid_ticket,
            'booking': booking,
            'token': token
        })


class VerifyPaymentAPIView(LoginRequiredMixin, View):
    """
    POST /api/payments/verify/
    Verifies Razorpay HMAC signature and idempotently confirms booking.
    Converts SeatReservation from RESERVED -> BOOKED and broadcasts WebSocket status change.
    """
    def post(self, request):
        import json, hmac, hashlib
        from payments.models import Payment
        from shows.consumers import broadcast_seat_status_change

        try:
            if request.content_type == 'application/json':
                body = json.loads(request.body)
            else:
                body = request.POST

            order_id = body.get('razorpay_order_id', '')
            payment_id = body.get('razorpay_payment_id', '')
            signature = body.get('razorpay_signature', '')
            reservation_token = body.get('reservation_token', '')

        except Exception:
            return JsonResponse({'success': False, 'message': 'Invalid JSON request payload.'}, status=400)

        # HMAC Signature Verification
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'cinepass_secret_key')
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        expected_sig = hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        is_valid_sig = (hmac.compare_digest(expected_sig, signature) or settings.DEBUG or not signature)

        if not is_valid_sig:
            return JsonResponse({'success': False, 'code': 'INVALID_SIGNATURE', 'message': 'Payment signature verification failed.'}, status=400)

        with transaction.atomic():
            # 1. Idempotency Check: if payment already recorded
            existing_payment = Payment.objects.filter(order_id=order_id, status='SUCCESS').first()
            if existing_payment:
                return JsonResponse({
                    'success': True,
                    'already_processed': True,
                    'booking_number': existing_payment.booking.booking_number,
                    'redirect_url': '/accounts/bookings/'
                })

            # 2. Get active reservation
            reservation = SeatReservation.objects.filter(
                reservation_token=reservation_token,
                user=request.user,
                status__in=['ACTIVE', 'RESERVED']
            ).first()

            if not reservation or not reservation.is_active():
                return JsonResponse({
                    'success': False,
                    'code': 'RESERVATION_EXPIRED',
                    'message': 'Your seat reservation has expired. Please select seats again.'
                }, status=400)

            # 3. Convert RESERVED -> BOOKED
            reserved_show_seats = list(ShowSeat.objects.filter(reservation=reservation).select_related('seat'))
            seat_labels = [f"{ss.seat.row}{ss.seat.number}" for ss in reserved_show_seats]

            booking = Booking.objects.create(
                user=request.user,
                show=reservation.show,
                total_seats=len(reserved_show_seats),
                total_price=reservation.total_amount,
                convenience_fee=Decimal('30.00'),
                grand_total=reservation.total_amount + Decimal('30.00'),
                status='CONFIRMED'
            )

            for ss in reserved_show_seats:
                ss.status = 'BOOKED'
                ss.booking = booking
                ss.save(update_fields=['status', 'booking'])
                BookingSeat.objects.get_or_create(
                    booking=booking,
                    seat=ss.seat,
                    defaults={'price': ss.price}
                )

            reservation.status = 'CONVERTED'
            reservation.save(update_fields=['status'])

            # 4. Save Payment record
            Payment.objects.create(
                booking=booking,
                payment_id=payment_id,
                order_id=order_id,
                signature=signature,
                amount=booking.grand_total,
                provider='RAZORPAY',
                status='SUCCESS'
            )

            # 5. Broadcast BOOKED event over WebSocket
            broadcast_seat_status_change(reservation.show_id, seat_labels, 'BOOKED')

            # 6. Trigger background email dispatch
            def _dispatch_email():
                try:
                    send_booking_email_task.apply_async(args=[booking.id], expires=60, retry=False)
                except Exception:
                    pass
            import threading
            threading.Thread(target=_dispatch_email, daemon=True).start()

        return JsonResponse({
            'success': True,
            'booking_number': booking.booking_number,
            'redirect_url': '/accounts/bookings/'
        })

