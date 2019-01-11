from django.urls import path
from . import views

urlpatterns = [
    path('updates', views.SiteUpdateView.as_view(), name='site_updates'),
    path('updates/<int:page>', views.SiteUpdateView.as_view(), name='site_updates'),
    path('report_bug', views.BugReportView.as_view(), name='site_bugreport'),
]