from django.urls import path

from .views import DashboardView, ReportListView, ReportView

urlpatterns = [
    path("dashboard", DashboardView.as_view(), name="dashboard"),
    path("reports", ReportListView.as_view(), name="reports"),
    path("reports/<slug:key>", ReportView.as_view(), name="report"),
]
