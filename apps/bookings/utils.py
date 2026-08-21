import io
import logging
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.conf import settings

logger = logging.getLogger(__name__)

# Safe optional imports with fallback
try:
    import qrcode
except ImportError:
    qrcode = None

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
except ImportError:
    SimpleDocTemplate = None


def generate_ticket_signature_token(booking):
    """
    Generates a secure, signed verification token for a booking.
    """
    signer = TimestampSigner()
    payload = f"{booking.id}:{booking.booking_number}:{booking.user_id}"
    return signer.sign(payload)


def verify_ticket_signature_token(token, max_age_days=30):
    """
    Verifies signed verification token and returns (is_valid, payload_dict or None).
    """
    signer = TimestampSigner()
    try:
        unsigned = signer.unsign(token, max_age=86400 * max_age_days)
        parts = unsigned.split(':')
        if len(parts) >= 3:
            return True, {
                'booking_id': int(parts[0]),
                'booking_number': parts[1],
                'user_id': int(parts[2])
            }
    except (BadSignature, SignatureExpired, ValueError) as e:
        logger.warning(f"Invalid or expired ticket verification token: {e}")
    return False, None


def generate_qr_code_bytes(booking):
    """
    Generates a PNG byte stream for a QR code containing ticket verification URL.
    """
    if not qrcode:
        logger.warning("qrcode package not installed. Skipping QR code rendering.")
        return None

    token = generate_ticket_signature_token(booking)
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:8000')
    verification_url = f"{frontend_url}/bookings/tickets/verify/{token}/"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(verification_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#e11d48", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def generate_pdf_ticket(booking):
    """
    Generates a professional PDF ticket using ReportLab with movie details, venue, showtime, QR code, and payment status.
    Returns bytes of the generated PDF file.
    """
    if not SimpleDocTemplate:
        logger.warning("ReportLab package not installed. Returning fallback ticket text.")
        return f"CinePass Ticket Reference #{booking.booking_number}\nMovie: {booking.show.movie.title}\nSeats: {booking.total_seats}".encode('utf-8')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    CRIMSON = colors.HexColor('#e11d48')
    DARK_BG = colors.HexColor('#0f172a')
    SLATE = colors.HexColor('#64748b')

    title_style = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=CRIMSON,
        alignment=0,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=SLATE,
        spaceAfter=15
    )

    label_style = ParagraphStyle(
        'FieldLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=SLATE
    )

    val_style = ParagraphStyle(
        'FieldValue',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=DARK_BG
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("CINEPASS E-TICKET", title_style))
    story.append(Paragraph(f"Official Admission Ticket • Reference #{booking.booking_number}", subtitle_style))
    story.append(Spacer(1, 10))

    # 2. QR Code Generation
    qr_buffer = generate_qr_code_bytes(booking)
    if qr_buffer:
        qr_img = RLImage(qr_buffer, width=120, height=120)
        right_table_data = [
            [qr_img],
            [Paragraph("<font color='#e11d48'><b>SCAN TO VERIFY</b></font>", ParagraphStyle('Scan', parent=styles['Normal'], fontSize=8, alignment=1))]
        ]
    else:
        right_table_data = [
            [Paragraph("<b>CINEPASS</b>", ParagraphStyle('Ref', parent=styles['Normal'], fontSize=12, textColor=CRIMSON))]
        ]

    # Fetch seat assignments
    booked_seats = list(booking.booked_seats.select_related('seat').all())
    seat_labels = ", ".join([f"{bs.seat.row}{bs.seat.number}" for bs in booked_seats]) if booked_seats else f"{booking.total_seats} Seat(s)"

    # 3. Main Ticket Grid Data
    movie_info = [
        [Paragraph("MOVIE TITLE", label_style), Paragraph("SHOWTIME & DATE", label_style)],
        [Paragraph(f"<b>{booking.show.movie.title}</b>", val_style), Paragraph(booking.show.start_time.strftime('%A, %b %d, %Y at %I:%M %p'), val_style)],
        [Spacer(1, 8), Spacer(1, 8)],
        [Paragraph("THEATER VENUE", label_style), Paragraph("CITY / LOCATION", label_style)],
        [Paragraph(f"<b>{booking.show.screen.theater.name}</b> ({booking.show.screen.name})", val_style), Paragraph(f"{booking.show.screen.theater.city.name}", val_style)],
        [Spacer(1, 8), Spacer(1, 8)],
        [Paragraph("BOOKED SEATS", label_style), Paragraph("TOTAL PAYMENT", label_style)],
        [Paragraph(f"<b>{seat_labels}</b>", val_style), Paragraph(f"<b>₹{booking.grand_total}</b> ({booking.status})", val_style)],
    ]

    left_table = Table(movie_info, colWidths=[220, 220])
    left_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 2),
    ]))

    right_table = Table(right_table_data, colWidths=[130])
    right_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    ticket_layout = Table([[left_table, right_table]], colWidths=[440, 130])
    ticket_layout.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 1.5, CRIMSON),
        ('PADDING', (0, 0), (-1, -1), 16),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    story.append(ticket_layout)
    story.append(Spacer(1, 20))

    notice_text = (
        "<b>Important Boarding & Admission Information:</b><br/>"
        "• Please present this PDF ticket or QR code at the theater entrance scanner.<br/>"
        "• Admission is subject to age ratings and theater security policies.<br/>"
        "• For questions, cancellations, or support, visit your CinePass profile dashboard."
    )
    story.append(Paragraph(notice_text, ParagraphStyle('Notice', parent=styles['Normal'], fontSize=8, textColor=SLATE, leading=11)))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
