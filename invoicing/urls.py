from django.urls import path

from invoicing import views

urlpatterns = [
    path('upgrade/', views.UpgradeBalanceView.as_view(), name='invoicing-upgrade'),
    path('reports/<slug:association_name>/', views.ReportsView.as_view(), name='invoicing-reports'),
    path('reports/<slug:association_name>/new/', views.CreateReportView.as_view(), name='invoicing-new-report'),
    path('download/<int:pk>/', views.ReportDownloadView.as_view(), name='invoicing-report-download'),
]
