from django.urls import path
from .views import AdminDashboardView, ExportAnalyticsCSVView

app_name = 'dashboard'

urlpatterns = [
    path('', AdminDashboardView.as_view(), name='admin_dashboard'),
    path('export-csv/', ExportAnalyticsCSVView.as_view(), name='export_csv'),
]
