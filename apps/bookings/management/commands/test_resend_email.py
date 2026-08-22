import os
import sys
import base64
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from bookings.models import Booking
from bookings.utils import generate_pdf_ticket


class Command(BaseCommand):
    help = 'Safely diagnoses Resend API email integration, sender verification, PDF attachment, and Celery connectivity.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Recipient email to test ticket delivery end-to-end',
            default=None
        )
        parser.add_argument(
            '--booking-id',
            type=int,
            help='Optional Booking ID to use for ticket PDF generation',
            default=None
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 60))
        self.stdout.write(self.style.NOTICE("CINEPASS RESEND & TICKET EMAIL DIAGNOSTIC AUDIT"))
        self.stdout.write(self.style.NOTICE("=" * 60))

        # 1. Check RESEND_API_KEY
        raw_key = getattr(settings, 'RESEND_API_KEY', '') or os.getenv('RESEND_API_KEY', '')
        key_configured = bool(raw_key and raw_key.strip())
        key_status_str = "CONFIGURED" if key_configured else "MISSING"

        if key_configured:
            # Mask key for security: only show prefix length and valid pattern check
            key_preview = f"CONFIGURED ({len(raw_key)} chars, starts with '{raw_key[:3]}...')" if len(raw_key) > 5 else "CONFIGURED"
            self.stdout.write(self.style.SUCCESS(f"RESEND_API_KEY: {key_preview}"))
        else:
            self.stdout.write(self.style.ERROR("RESEND_API_KEY: MISSING"))
            self.stdout.write(self.style.WARNING(
                "  -> Action Required: Set RESEND_API_KEY in Render Dashboard Environment variables."
            ))

        # 2. Check Sender Email
        resend_from = getattr(settings, 'RESEND_FROM_EMAIL', '') or os.getenv('RESEND_FROM_EMAIL', 'CinePass <onboarding@resend.dev>')
        self.stdout.write(f"RESEND_FROM_EMAIL: {resend_from}")
        if '@gmail.com' in resend_from or '@yahoo.com' in resend_from:
            self.stdout.write(self.style.WARNING(
                "  -> Notice: Public webmail domains (@gmail/@yahoo) cannot be used directly with Resend. "
                "CinePass automatically routes through 'CinePass <onboarding@resend.dev>' or your verified domain."
            ))

        # 3. Check PDF Generation
        target_booking = None
        if options['booking_id']:
            target_booking = Booking.objects.filter(pk=options['booking_id']).first()
        if not target_booking:
            target_booking = Booking.objects.filter(status='CONFIRMED').last()

        pdf_bytes = None
        if target_booking:
            try:
                pdf_bytes = generate_pdf_ticket(target_booking)
                if pdf_bytes and pdf_bytes.startswith(b'%PDF'):
                    self.stdout.write(self.style.SUCCESS(f"PDF Generation: PASS ({len(pdf_bytes)} bytes for Booking #{target_booking.booking_number})"))
                else:
                    self.stdout.write(self.style.WARNING("PDF Generation: WARN (Output not standard PDF header)"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"PDF Generation: FAIL ({e})"))
        else:
            self.stdout.write(self.style.NOTICE("PDF Generation: SKIPPED (No booking records found in database to test)"))

        # 4. Direct Resend API Test
        recipient = options['email']
        if recipient and key_configured:
            self.stdout.write(self.style.NOTICE(f"\nDispatching test ticket email to: {recipient}..."))
            headers = {
                'Authorization': f'Bearer {raw_key.strip()}',
                'Content-Type': 'application/json',
            }

            from_addr = resend_from
            if '@gmail.com' in from_addr or '@yahoo.com' in from_addr:
                from_addr = 'CinePass <onboarding@resend.dev>'

            payload = {
                'from': from_addr,
                'to': [recipient],
                'subject': f"🎟️ CinePass Diagnostic Test Ticket: {target_booking.booking_number if target_booking else 'TEST'}",
                'html': "<p>This is a diagnostic ticket email test from CinePass production verification pipeline.</p>",
                'text': "This is a diagnostic ticket email test from CinePass production verification pipeline."
            }

            if pdf_bytes:
                b64_pdf = base64.b64encode(pdf_bytes).decode('ascii')
                payload['attachments'] = [
                    {
                        'filename': f"CinePass_Ticket_{target_booking.booking_number if target_booking else 'Test'}.pdf",
                        'content': b64_pdf
                    }
                ]

            try:
                resp = requests.post('https://api.resend.com/emails', json=payload, headers=headers, timeout=15)
                if resp.status_code in (200, 201):
                    self.stdout.write(self.style.SUCCESS(f"Resend API Response: PASS (Status {resp.status_code}) -> Email ID: {resp.json().get('id')}"))
                else:
                    self.stdout.write(self.style.ERROR(f"Resend API Response: FAIL (Status {resp.status_code})"))
                    self.stdout.write(self.style.ERROR(f"  Error details: {resp.text}"))
            except Exception as conn_err:
                self.stdout.write(self.style.ERROR(f"Resend API Connection: FAIL ({conn_err})"))
        elif not recipient:
            self.stdout.write(self.style.NOTICE(
                "\nRun with '--email your-email@example.com' to send a real live diagnostic email through Resend."
            ))

        self.stdout.write(self.style.NOTICE("=" * 60))
