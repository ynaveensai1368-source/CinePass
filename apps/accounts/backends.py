from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend allowing users to log in using either
    their email address or their username (case-insensitively).
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD) or kwargs.get('email')
        if username is None or password is None:
            return None

        clean_username = username.strip()
        try:
            user = User.objects.filter(
                Q(email__iexact=clean_username) | Q(username__iexact=clean_username)
            ).first()
            if user and user.check_password(password) and self.user_can_authenticate(user):
                return user
        except Exception:
            return None
        return None
