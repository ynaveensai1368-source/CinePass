from django.contrib import admin
from .models import City, Theater, Screen, Seat

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'state', 'slug')
    search_fields = ('name', 'state')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Theater)
class TheaterAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'city', 'is_active', 'created_at')
    list_filter = ('city', 'is_active')
    search_fields = ('name', 'address', 'city__name')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'theater', 'screen_type', 'total_seats')
    list_filter = ('screen_type', 'theater__city', 'theater')
    search_fields = ('name', 'theater__name')

@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ('id', 'screen', 'row', 'number', 'seat_type', 'is_active')
    list_filter = ('seat_type', 'is_active', 'screen__theater')
    search_fields = ('row', 'number', 'screen__name', 'screen__theater__name')
