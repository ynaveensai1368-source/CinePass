from django.urls import path
from .views import TheaterListView, TheaterCreateView, ShowCreateView

app_name = 'theaters'

urlpatterns = [
    path('', TheaterListView.as_view(), name='list'),
    path('add/', TheaterCreateView.as_view(), name='create'),
    path('show/add/', ShowCreateView.as_view(), name='create_show'),
]
