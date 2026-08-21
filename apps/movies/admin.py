from django.contrib import admin
from .models import Genre, Language, Cast, Movie, Poster, RecentlyViewed

@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'code')
    search_fields = ('name', 'code')

@admin.register(Cast)
class CastAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'character_name', 'tmdb_id')
    search_fields = ('name', 'character_name')

@admin.register(Poster)
class PosterAdmin(admin.ModelAdmin):
    list_display = ('id', 'movie', 'is_primary', 'created_at')
    list_filter = ('is_primary', 'created_at')
    search_fields = ('movie__title',)

class PosterInline(admin.TabularInline):
    model = Poster
    extra = 1

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'category', 'certificate', 'language', 'duration', 'release_date', 'rating', 'popularity', 'is_active')
    list_filter = ('category', 'certificate', 'language', 'genres', 'is_active', 'release_date')
    search_fields = ('title', 'description', 'director')
    prepopulated_fields = {'slug': ('title',)}
    ordering = ('-popularity', '-release_date')
    filter_horizontal = ('genres', 'cast_members')
    inlines = [PosterInline]
    list_editable = ('rating', 'popularity', 'is_active')
    list_per_page = 20

@admin.register(RecentlyViewed)
class RecentlyViewedAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'movie', 'viewed_at')
    list_filter = ('viewed_at',)
    search_fields = ('user__email', 'movie__title', 'session_key')
    ordering = ('-viewed_at',)
