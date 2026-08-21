from django.urls import path
from .views import (
    HomeView, MovieDiscoveryView, MovieDetailView,
    MovieCreateView, MovieUpdateView, MovieDeleteView,
    MovieAPIDiscoveryView
)

app_name = 'movies'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('discover/', MovieDiscoveryView.as_view(), name='discovery'),
    path('api/movies/', MovieAPIDiscoveryView.as_view(), name='api_discovery'),
    path('movie/<slug:slug>/', MovieDetailView.as_view(), name='detail'),
    path('movie/add/new/', MovieCreateView.as_view(), name='create'),
    path('movie/<slug:slug>/edit/', MovieUpdateView.as_view(), name='update'),
    path('movie/<slug:slug>/delete/', MovieDeleteView.as_view(), name='delete'),
]

