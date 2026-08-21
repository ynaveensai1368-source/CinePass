from django.urls import path
from .views import MovieReviewsListAPIView, CreateOrUpdateReviewAPIView, ReportReviewAPIView

app_name = 'reviews'

urlpatterns = [
    path('api/movie/<int:movie_id>/', MovieReviewsListAPIView.as_view(), name='api_movie_reviews'),
    path('api/movie/<int:movie_id>/add/', CreateOrUpdateReviewAPIView.as_view(), name='api_add_review'),
    path('api/review/<int:review_id>/report/', ReportReviewAPIView.as_view(), name='api_report_review'),
]
