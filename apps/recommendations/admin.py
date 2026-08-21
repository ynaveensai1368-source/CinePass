from django.contrib import admin
from .models import UserInteraction

@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'movie', 'interaction_type', 'score_weight', 'created_at')
    list_filter = ('interaction_type', 'created_at')
    search_fields = ('user__email', 'session_key', 'movie__title')
    ordering = ('-created_at',)
