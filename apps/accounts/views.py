from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView, ListView, View
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages

from .models import User
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm
from bookings.models import Booking

class RegisterView(CreateView):
    model = User
    form_class = UserRegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('movies:home')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend='accounts.backends.EmailOrUsernameModelBackend')
        messages.success(self.request, f"Welcome to Movie Discovery, {user.first_name or user.username}! Account created successfully.")
        return redirect(self.success_url)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('movies:home')
        return super().dispatch(request, *args, **kwargs)


class CustomLoginView(LoginView):
    form_class = UserLoginForm
    template_name = 'accounts/login.html'

    def form_valid(self, form):
        messages.success(self.request, "Logged in successfully!")
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('movies:home')
        return super().dispatch(request, *args, **kwargs)


class CustomLogoutView(View):
    def get(self, request):
        logout(request)
        messages.info(request, "You have been logged out successfully.")
        return redirect('movies:home')

    def post(self, request):
        logout(request)
        messages.info(request, "You have been logged out successfully.")
        return redirect('movies:home')


class ProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = UserProfileForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Your profile has been updated successfully.")
        return super().form_valid(form)


class BookingHistoryView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'accounts/booking_history.html'
    context_object_name = 'bookings'
    paginate_by = 10

    def get_queryset(self):
        return Booking.objects.filter(
            user=self.request.user
        ).select_related(
            'show__movie',
            'show__screen__theater',
            'show__screen__theater__city'
        ).prefetch_related(
            'show__movie__genres'
        ).order_by('-created_at')


class PaymentHistoryView(LoginRequiredMixin, ListView):
    """
    Dedicated view for authenticated users to view all payment transactions,
    gateway order IDs, payment status badges, and transaction timestamps.
    """
    template_name = 'accounts/payment_history.html'
    context_object_name = 'payments'
    paginate_by = 10

    def get_queryset(self):
        from payments.models import Payment
        return Payment.objects.filter(
            booking__user=self.request.user
        ).select_related(
            'booking__show__movie',
            'booking__show__screen__theater',
            'booking__show__screen__theater__city'
        ).order_by('-created_at')


class GoogleLoginRedirectView(View):
    """
    Initiates Google OAuth 2.0 Authorization Code flow.
    Builds the Google OAuth URL with dynamic redirect_uri matching current host.
    """
    def get(self, request):
        import secrets
        import urllib.parse
        from django.conf import settings

        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '').strip()
        if not client_id:
            messages.error(request, "Google OAuth is not configured yet. Please use regular email/password login.")
            return redirect('accounts:login')

        # Store next destination URL in session
        next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'
        request.session['google_oauth_next'] = next_url

        # Cryptographically secure state parameter to prevent CSRF
        state = secrets.token_urlsafe(32)
        request.session['google_oauth_state'] = state

        from django.urls import reverse
        redirect_uri = request.build_absolute_uri(reverse('accounts:google_callback'))

        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'online',
            'state': state,
            'prompt': 'select_account',
        }

        google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
        return redirect(google_auth_url)


class GoogleLoginCallbackView(View):
    """
    Handles Google OAuth 2.0 callback, exchanges authorization code for tokens,
    retrieves user profile from Google OpenID UserInfo, and logs in or creates the user.
    """
    def get(self, request):
        import requests
        from django.conf import settings
        from django.urls import reverse

        # 1. Check for OAuth errors from Google
        error = request.GET.get('error')
        if error:
            messages.warning(request, f"Google login was cancelled or encountered an error ({error}).")
            return redirect('accounts:login')

        code = request.GET.get('code')
        state = request.GET.get('state')
        saved_state = request.session.pop('google_oauth_state', None)

        if not code or not state or state != saved_state:
            messages.error(request, "Invalid or expired Google authentication session. Please try again.")
            return redirect('accounts:login')

        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '').strip()
        client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '').strip()
        redirect_uri = request.build_absolute_uri(reverse('accounts:google_callback'))

        # 2. Exchange authorization code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_payload = {
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }

        try:
            token_resp = requests.post(token_url, data=token_payload, timeout=10)
            token_data = token_resp.json()
        except Exception as net_err:
            messages.error(request, f"Could not connect to Google verification service: {net_err}")
            return redirect('accounts:login')

        if token_resp.status_code != 200 or 'access_token' not in token_data:
            error_desc = token_data.get('error_description') or token_data.get('error') or 'Token exchange failed'
            messages.error(request, f"Google authentication failed: {error_desc}")
            return redirect('accounts:login')

        access_token = token_data['access_token']

        # 3. Retrieve Google User Info
        userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
        try:
            userinfo_resp = requests.get(
                userinfo_url,
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            userinfo = userinfo_resp.json()
        except Exception as net_err:
            messages.error(request, f"Failed to retrieve user profile from Google: {net_err}")
            return redirect('accounts:login')

        email = userinfo.get('email', '').strip().lower()
        if not email:
            messages.error(request, "Google profile did not provide a valid email address.")
            return redirect('accounts:login')

        given_name = userinfo.get('given_name') or userinfo.get('name', '').split(' ')[0]
        family_name = userinfo.get('family_name') or ''
        
        # 4. Find or Create User Account
        user = User.objects.filter(email__iexact=email).first()
        is_new_user = False

        if not user:
            # Generate unique username from email/name
            base_username = email.split('@')[0].replace('.', '_')
            username = base_username
            counter = 1
            while User.objects.filter(username__iexact=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            user = User.objects.create(
                username=username,
                email=email,
                first_name=given_name,
                last_name=family_name,
                role='CUSTOMER',
                is_active=True
            )
            user.set_unusable_password()
            user.save()
            is_new_user = True
        else:
            # Update missing names if available
            updated_fields = []
            if not user.first_name and given_name:
                user.first_name = given_name
                updated_fields.append('first_name')
            if not user.last_name and family_name:
                user.last_name = family_name
                updated_fields.append('last_name')
            if updated_fields:
                user.save(update_fields=updated_fields)

        # 5. Log in user
        login(request, user, backend='accounts.backends.EmailOrUsernameModelBackend')

        if is_new_user:
            messages.success(request, f"🎉 Welcome to CinePass, {user.first_name or user.username}! Your Google account is now linked.")
        else:
            messages.success(request, f"Welcome back, {user.first_name or user.username}! Logged in via Google.")

        next_url = request.session.pop('google_oauth_next', '/')
        if not next_url or not next_url.startswith('/'):
            next_url = '/'
        return redirect(next_url)

