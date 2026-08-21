from django.contrib import admin
from .models import Booking, BookingSeat

class BookingSeatInline(admin.TabularInline):
    model = BookingSeat
    extra = 0
    readonly_fields = ('seat', 'price')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking_number', 'user', 'show', 'total_seats', 'grand_total', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'show__screen__theater__city')
    search_fields = ('booking_number', 'user__email', 'show__movie__title', 'show__screen__theater__name')
    ordering = ('-created_at',)
    readonly_fields = ('booking_number', 'created_at', 'updated_at', 'grand_total')
    inlines = [BookingSeatInline]

@admin.register(BookingSeat)
class BookingSeatAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'seat', 'price')
    search_fields = ('booking__booking_number', 'seat__row', 'seat__number')
