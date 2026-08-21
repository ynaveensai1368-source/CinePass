from django.contrib import admin
from .models import Show, SeatReservation, ShowSeat


@admin.register(Show)
class ShowAdmin(admin.ModelAdmin):
    list_display = ('id', 'movie', 'screen', 'start_time', 'base_price', 'status', 'available_seats')
    list_filter = ('status', 'screen__theater__city', 'screen__theater', 'start_time')
    search_fields = ('movie__title', 'screen__theater__name', 'screen__name')
    ordering = ('start_time',)
    list_editable = ('base_price', 'status', 'available_seats')


@admin.register(SeatReservation)
class SeatReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'reservation_token', 'user', 'show', 'seat', 'status', 'total_amount', 'reserved_at', 'expires_at')
    list_filter = ('status', 'show__screen__theater', 'reserved_at', 'expires_at')
    search_fields = ('reservation_token', 'user__email', 'user__username', 'seat__row', 'seat__number', 'show__movie__title')
    ordering = ('-reserved_at',)


@admin.register(ShowSeat)
class ShowSeatAdmin(admin.ModelAdmin):
    list_display = ('id', 'show', 'seat', 'status', 'price', 'reservation', 'booking')
    list_filter = ('status', 'seat__seat_type', 'show__screen__theater')
    search_fields = ('seat__row', 'seat__number', 'show__movie__title', 'show__screen__theater__name')
    ordering = ('show', 'seat__row', 'seat__number')
