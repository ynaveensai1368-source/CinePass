"""
Robust image normalization and fallback utilities for CinePass.
Ensures valid, secure HTTPS URLs for posters and backdrops from TMDb, local media, and fallbacks.
"""
import re
import logging

logger = logging.getLogger(__name__)

FALLBACK_POSTER = '/static/images/fallback_poster.png'
FALLBACK_BACKDROP = '/static/images/fallback_poster.png'


def normalize_image_url(url, size='w500', is_backdrop=False):
    """
    Normalizes any image URL or TMDb relative path into a secure, fully-qualified HTTPS URL.
    
    Handles:
      - Empty / None / 'null' -> returns appropriate fallback URL.
      - Relative TMDb paths: '/abc123xyz.jpg' or 'abc123xyz.jpg' -> 'https://image.tmdb.org/t/p/{size}/abc123xyz.jpg'
      - Insecure HTTP -> auto-upgrades to HTTPS to prevent browser mixed-content blocking.
      - Local media / static paths: '/media/posters/...' or '/static/...' -> preserved.
      - Full remote HTTPS URLs -> cleaned and returned.
    """
    fallback = FALLBACK_BACKDROP if is_backdrop else FALLBACK_POSTER

    if not url:
        return fallback

    url = str(url).strip()
    if not url or url.lower() in ('none', 'null', 'undefined', '#', ''):
        return fallback

    # Upgrade insecure HTTP to HTTPS for SSL compliance
    if url.startswith('http://'):
        url = 'https://' + url[7:]

    # Valid HTTPS URL or protocol-relative URL
    if url.startswith('https://') or url.startswith('//'):
        return url

    # Local static or media paths
    if url.startswith('/static/') or url.startswith('/media/'):
        return url

    # Clean relative TMDb file paths (e.g. '/abc.jpg' or 'abc.jpg')
    clean_path = url.lstrip('/')
    if '.' in clean_path and any(clean_path.lower().endswith(ext) for ext in ('.jpg', '.jpeg', '.png', '.webp', '.svg')):
        # Choose default TMDb CDN size
        target_size = size if size else ('w1280' if is_backdrop else 'w500')
        return f"https://image.tmdb.org/t/p/{target_size}/{clean_path}"

    return fallback
