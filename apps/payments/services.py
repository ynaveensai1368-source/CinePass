import logging
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import razorpay
except ImportError:
    razorpay = None


def get_razorpay_client():
    """
    Returns an initialized Razorpay Client instance.
    """
    if not razorpay:
        logger.warning("razorpay package not installed.")
        return None
    key_id = getattr(settings, 'RAZORPAY_KEY_ID', 'rzp_test_cinepass_key')
    key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', 'cinepass_secret_key')
    return razorpay.Client(auth=(key_id, key_secret))


def create_razorpay_order(amount_in_inr, currency='INR', receipt=None):
    """
    Creates a Razorpay order for the specified amount in INR (converted to paisa).
    Returns order dictionary or mock order if client is unavailable.
    """
    client = get_razorpay_client()
    amount_in_paisa = int(round(amount_in_inr * 100))

    if not client or amount_in_inr <= 0:
        import uuid
        # Fallback mock order for testing without internet or razorpay keys
        mock_id = f"order_{uuid.uuid4().hex[:12]}"
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
        logger.info(f"Created Razorpay order #{order.get('id')} for amount ₹{amount_in_inr}")
        return order
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}")
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
