import logging
import time
from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from .models import Booking
from .utils import generate_pdf_ticket

logger = logging.getLogger(__name__)


def send_booking_email(booking_id):
    """
    Generates official PDF ticket and sends a beautifully formatted confirmation email to customer.
    Includes automatic retries for database sync and SMTP connection resilience.
    """
    booking = None
    # Retry fetching booking in case the database transaction is committing
    for attempt in range(3):
        try:
            booking = Booking.objects.select_related(
                'show__movie', 'show__screen__theater', 'show__screen__theater__city', 'user'
            ).get(pk=booking_id)
            break
        except Exception:
            time.sleep(0.3)

    if not booking:
        logger.error(f"Could not find Booking #{booking_id} for email delivery.")
        return False

    user_email = (booking.user.email or '').strip()
    if not user_email or '@' not in user_email:
        if '@' in booking.user.username:
            user_email = booking.user.username
        else:
            user_email = getattr(settings, 'EMAIL_HOST_USER', 'ynaveensai1368@gmail.com')

    user_name = booking.user.first_name or booking.user.username or 'Movie Lover'
    movie_title = booking.show.movie.title
    theater_name = booking.show.screen.theater.name
    city_name = booking.show.screen.theater.city.name
    screen_name = booking.show.screen.name
    show_time_str = booking.show.start_time.strftime('%A, %b %d, %Y at %I:%M %p')

    # Fetch seat assignments
    booked_seats = list(booking.booked_seats.select_related('seat').all())
    seat_labels = ", ".join([f"{bs.seat.row}{bs.seat.number}" for bs in booked_seats]) if booked_seats else f"{booking.total_seats} Seat(s)"

    # Subject line
    subject = f"🎟️ CinePass E-Ticket Confirmed: {movie_title} (#{booking.booking_number})"

    # Plain text body
    text_body = f"""Dear {user_name},

Thank you for booking with CinePass! Your ticket reservation for '{movie_title}' is CONFIRMED.

==================================================
TICKET DETAILS
==================================================
Booking Reference: #{booking.booking_number}
Movie: {movie_title}
Theater: {theater_name} ({city_name})
Screen: {screen_name}
Showtime: {show_time_str}
Seats: {seat_labels}
Total Paid: ₹{booking.grand_total} (Status: {booking.status})

Your official admission e-ticket with QR code is attached as a PDF to this email.
Please present the PDF ticket or QR code at the theater entrance.

Enjoy your movie!
The CinePass Team
https://cinepass-r9o8.onrender.com/
"""

    # Rich HTML body
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0f19; color: #f8fafc; margin: 0; padding: 20px; }}
  .card {{ max-width: 600px; margin: 0 auto; background-color: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
  .header {{ background: linear-gradient(135deg, #e11d48 0%, #be123c 100%); padding: 28px; text-align: center; }}
  .header h1 {{ margin: 0; color: #ffffff; font-size: 24px; font-weight: 800; letter-spacing: 0.5px; }}
  .header p {{ margin: 6px 0 0 0; color: #ffe4e6; font-size: 14px; }}
  .content {{ padding: 28px; }}
  .movie-title {{ font-size: 22px; font-weight: 700; color: #ffffff; margin: 0 0 16px 0; border-bottom: 2px solid #e11d48; padding-bottom: 8px; }}
  .grid {{ display: table; width: 100%; margin-bottom: 20px; }}
  .row {{ display: table-row; }}
  .cell {{ display: table-cell; padding: 8px 12px; font-size: 14px; }}
  .cell-label {{ color: #94a3b8; font-weight: 600; width: 35%; }}
  .cell-value {{ color: #f8fafc; font-weight: 700; }}
  .badge {{ background-color: #10b981; color: #ffffff; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 700; }}
  .highlight-box {{ background-color: #0f172a; border-left: 4px solid #e11d48; border-radius: 8px; padding: 14px 18px; margin: 18px 0; }}
  .footer {{ background-color: #0f172a; padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #334155; }}
</style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>🎟️ CinePass E-Ticket</h1>
      <p>Booking Confirmed • Reference #{booking.booking_number}</p>
    </div>
    <div class="content">
      <p style="color: #cbd5e1; font-size: 15px;">Hello <b>{user_name}</b>,</p>
      <p style="color: #cbd5e1; font-size: 14px;">Your movie tickets have been confirmed! Here is your booking summary:</p>
      
      <div class="movie-title">🎬 {movie_title}</div>
      
      <div class="grid">
        <div class="row">
          <div class="cell cell-label">Theater</div>
          <div class="cell cell-value">{theater_name} ({city_name})</div>
        </div>
        <div class="row">
          <div class="cell cell-label">Screen</div>
          <div class="cell cell-value">{screen_name}</div>
        </div>
        <div class="row">
          <div class="cell cell-label">Showtime</div>
          <div class="cell cell-value">{show_time_str}</div>
        </div>
        <div class="row">
          <div class="cell cell-label">Seats</div>
          <div class="cell cell-value" style="color: #38bdf8;">{seat_labels} ({booking.total_seats} seats)</div>
        </div>
        <div class="row">
          <div class="cell cell-label">Total Amount</div>
          <div class="cell cell-value">₹{booking.grand_total} <span class="badge">PAID</span></div>
        </div>
      </div>

      <div class="highlight-box">
        <p style="margin: 0; color: #f1f5f9; font-size: 13px;">
          📎 <b>PDF E-Ticket Attached:</b> We have attached your official PDF admission ticket with verification QR code to this email. Please display it on your mobile device at the theater entrance.
        </p>
      </div>
    </div>
    <div class="footer">
      <p style="margin: 0 0 6px 0;">© 2026 CinePass Movie Discovery System</p>
      <p style="margin: 0;">Need help? Visit your <a href="https://cinepass-r9o8.onrender.com/accounts/bookings/" style="color: #e11d48; text-decoration: none;">Booking History</a> on CinePass.</p>
    </div>
  </div>
</body>
</html>
"""

    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'CinePass <ynaveensai1368@gmail.com>')

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=from_email,
        to=[user_email]
    )
    email.attach_alternative(html_body, "text/html")

    # Generate and attach PDF ticket
    try:
        pdf_bytes = generate_pdf_ticket(booking)
        if pdf_bytes:
            email.attach(f"CinePass_Ticket_{booking.booking_number}.pdf", pdf_bytes, 'application/pdf')
    except Exception as pdf_err:
        logger.warning(f"PDF ticket generation failed for booking #{booking_id}, sending text ticket email: {pdf_err}")

    # Send email with error logging
    try:
        sent_count = email.send(fail_silently=False)
        logger.info(f"✅ Successfully sent PDF ticket email for Booking #{booking.booking_number} to {user_email} (sent_count={sent_count})")
        return True
    except Exception as smtp_err:
        logger.error(f"❌ SMTP delivery error sending ticket email for Booking #{booking_id} to {user_email}: {smtp_err}")
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
