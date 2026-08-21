from django.contrib import admin
from .models import Review, ReviewReport


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'movie', 'rating', 'is_spoiler', 'likes_count', 'created_at')
    list_filter = ('rating', 'is_spoiler', 'created_at')
    search_fields = ('user__email', 'movie__title', 'headline', 'comment')
    ordering = ('-created_at',)


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'review', 'user', 'reason', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'review__movie__title', 'reason')
    ordering = ('-created_at',)
