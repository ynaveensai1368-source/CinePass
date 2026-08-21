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
        login(self.request, user)
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
