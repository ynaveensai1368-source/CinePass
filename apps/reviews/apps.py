from django.apps import AppConfig

class ReviewsConfig(AppConfig):
    default_auto_field: str = 'django.db.models.BigAutoField'  # type: ignore[assignment] # pyright: ignore[reportIncompatibleVariableOverride]
    name = 'reviews'
