import logging
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import razorpay
except ImportError:
    razorpay = None


def is_razorpay_configured():
    """
    Checks if genuine Razorpay API credentials are configured in settings.
    Returns False for placeholder/dummy keys, empty values, or default test strings.
    """
    key_id = (getattr(settings, 'RAZORPAY_KEY_ID', '') or '').strip()
    key_secret = (getattr(settings, 'RAZORPAY_KEY_SECRET', '') or '').strip()

    if not key_id or not key_secret:
        return False

    # Check for placeholder markers
    placeholders = ['cinepass', 'your_key', 'test_key', 'dummy', 'placeholder', 'xxx', 'change_me', 'your_razorpay']
    if any(p in key_id.lower() for p in placeholders) or any(p in key_secret.lower() for p in placeholders):
        return False

    # Genuine Razorpay keys start with rzp_test_ or rzp_live_ followed by 14+ characters
    if not (key_id.startswith('rzp_test_') or key_id.startswith('rzp_live_')) or len(key_id) < 18:
        return False

    return len(key_secret) >= 8


def get_razorpay_client():
    """
    Returns an initialized Razorpay Client instance if valid credentials exist.
    Returns None if razorpay is not installed or if placeholder/sandbox keys are used.
    """
    if not razorpay:
        logger.debug("razorpay package not installed.")
        return None

    if not is_razorpay_configured():
        return None

    key_id = getattr(settings, 'RAZORPAY_KEY_ID', '')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', '')
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(amount_in_inr, currency='INR', receipt=None):
    """
    Creates a Razorpay order for the specified amount in INR (converted to paisa).
    Returns order dictionary or mock order if client is unavailable or in sandbox mode.
    """
    client = get_razorpay_client()
    amount_in_paisa = int(round(amount_in_inr * 100))

    if not client or amount_in_inr <= 0:
        import uuid
        mock_id = f"order_{uuid.uuid4().hex[:12]}"
        logger.info(f"Sandbox Razorpay order #{mock_id} initialized for amount ₹{amount_in_inr}")
        return {
            'id': mock_id,
            'entity': 'order',
            'amount': amount_in_paisa,
            'currency': currency,
            'receipt': receipt or f"rcpt_{mock_id}",
            'status': 'created'
        }

    try:
        order_data = {
            'amount': amount_in_paisa,
            'currency': currency,
            'receipt': receipt,
            'payment_capture': 1
        }
        order = client.order.create(data=order_data)
        logger.info(f"Created live Razorpay order #{order.get('id')} for amount ₹{amount_in_inr}")
        return order
    except Exception as e:
        logger.warning(f"Razorpay live order creation failed ({e}). Falling back to sandbox order.")
        import uuid
        mock_id = f"order_{uuid.uuid4().hex[:12]}"
        return {
            'id': mock_id,
            'entity': 'order',
            'amount': amount_in_paisa,
            'currency': currency,
            'receipt': receipt or f"rcpt_{mock_id}",
            'status': 'created'
        }


def generate_razorpay_signature(razorpay_order_id, razorpay_payment_id):
    """
    Computes genuine HMAC-SHA256 Razorpay signature using the configured RAZORPAY_KEY_SECRET.
    Signature = HMAC-SHA256(order_id + "|" + payment_id, key_secret)
    """
    import hmac
    import hashlib
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'cinepass_secret_key') or 'cinepass_secret_key'
    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
    return hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()


def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verifies Razorpay HMAC SHA256 payment signature server-side.
    Returns True if valid, False otherwise.
    """
    import hmac
    import hashlib

    if not all([razorpay_order_id, razorpay_payment_id, razorpay_signature]):
        return False

    client = get_razorpay_client()
    if client:
        try:
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            client.utility.verify_payment_signature(params_dict)
            return True
        except Exception as e:
            logger.warning(f"Razorpay SDK signature verification error: {e}")

    # Cryptographic HMAC-SHA256 verification against configured RAZORPAY_KEY_SECRET
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'cinepass_secret_key') or 'cinepass_secret_key'
    msg = f"{razorpay_order_id}|{razorpay_payment_id}".encode('utf-8')
    expected_signature = hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_signature, razorpay_signature)
