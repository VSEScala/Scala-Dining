from django.urls import path

from reports import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsView.as_view(), name="index"),
    path("balance/", views.BalanceReportView.as_view(), name="balance"),
]
