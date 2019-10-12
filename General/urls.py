from django.urls import path

from General import views

urlpatterns = [
    path('updates/', views.SiteUpdateView.as_view(), name='site_updates'),
    path('help/', views.HelpPageView.as_view(), name='help_page'),
    path('report_bug/', views.BugReportView.as_view(), name='site_bugreport'),
    path('rules/', views.RulesPageView.as_view(), name='rules_and_regulations'),
    path('upgrade_instructions/', views.UpgradeBalanceInstructionsView.as_view(), name='upgrade_instructions'),
    path('mail_layout/', views.EmailTemplateView.as_view())
]
