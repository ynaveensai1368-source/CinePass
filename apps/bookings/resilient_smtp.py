import socket
import logging
from django.core.mail.backends.smtp import EmailBackend

logger = logging.getLogger(__name__)


class ResilientEmailBackend(EmailBackend):
    """
    Production-hardened Django SMTP EmailBackend.
    1. Enforces IPv4 DNS resolution (socket.AF_INET) to prevent '[Errno 101] Network is unreachable'
       on cloud containers (Render, AWS, Heroku) that lack IPv6 outbound routing.
    2. Automatically falls back from Port 587 (STARTTLS) to Port 465 (SSL) if port 587 has outbound restrictions.
    """
    def open(self):
        if self.connection:
            return False

        orig_getaddrinfo = socket.getaddrinfo

        def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            # Force IPv4 socket family
            return orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

        socket.getaddrinfo = ipv4_getaddrinfo
        try:
            return super().open()
        except Exception as primary_err:
            logger.warning(f"Primary SMTP connection ({self.host}:{self.port}) failed: {primary_err}")
            # If port 587 failed and SSL wasn't active, try port 465 SSL as fallback
            if not self.use_ssl:
                logger.info("Attempting automatic fallback to Port 465 with direct SSL...")
                orig_port = self.port
                orig_use_tls = self.use_tls
                orig_use_ssl = self.use_ssl

                self.port = 465
                self.use_ssl = True
                self.use_tls = False
                try:
                    res = super().open()
                    logger.info(f"✅ Fallback to Port 465 SSL succeeded!")
                    return res
                except Exception as fallback_err:
                    logger.error(f"Fallback to Port 465 SSL also failed: {fallback_err}")
                    # Restore original values
                    self.port = orig_port
                    self.use_tls = orig_use_tls
                    self.use_ssl = orig_use_ssl
                    if not self.fail_silently:
                        raise primary_err
            else:
                if not self.fail_silently:
                    raise primary_err
            return False
        finally:
            socket.getaddrinfo = orig_getaddrinfo
