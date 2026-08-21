import logging
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings

from .models import Booking
from .utils import generate_pdf_ticket

logger = logging.getLogger(__name__)


def send_booking_email(booking_id):
    """
    Direct helper function to generate PDF ticket and send e-ticket email to customer.
    Runs cleanly in-process or via background daemon thread when Celery is not active.
    """
    try:
        booking = Booking.objects.select_related(
            'show__movie', 'show__screen__theater', 'show__screen__theater__city', 'user'
        ).get(pk=booking_id)

        pdf_bytes = generate_pdf_ticket(booking)

        user_email = booking.user.email
        user_name = booking.user.first_name or booking.user.username
        movie_title = booking.show.movie.title
        theater_name = booking.show.screen.theater.name
        city_name = booking.show.screen.theater.city.name
        show_time_str = booking.show.start_time.strftime('%b %d, %Y at %I:%M %p')

        subject = f"🎟️ CinePass E-Ticket Confirmation - #{booking.booking_number} ({movie_title})"
        body = f"""Dear {user_name},

Thank you for booking with CinePass!

Your tickets for '{movie_title}' have been confirmed.

Show Details:
- Booking Reference: #{booking.booking_number}
- Movie: {movie_title}
- Theater: {theater_name} ({city_name})
- Screen: {booking.show.screen.name}
- Showtime: {show_time_str}
- Seats Booked: {booking.total_seats}
- Total Paid: INR {booking.grand_total}

Your official PDF ticket with verification QR code is attached to this email.

Enjoy the show!
The CinePass Team
"""
        email = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'CinePass <noreply@cinepass.com>'),
            to=[user_email]
        )
        email.attach(f"CinePass_Ticket_{booking.booking_number}.pdf", pdf_bytes, 'application/pdf')
        email.send(fail_silently=False)
        logger.info(f"Successfully sent PDF ticket email for Booking #{booking.booking_number} to {user_email}")
        return True
    except Exception as exc:
        logger.error(f"Error sending ticket email for Booking #{booking_id}: {exc}")
        return False


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_booking_email_task(self, booking_id):
    """
    Celery background task wrapper with automatic SMTP retries.
    """
    try:
        success = send_booking_email(booking_id)
        if not success:
            raise Exception("Failed to send email")
        return True
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
