from django.urls import path

from . import views

urlpatterns = [
    path('help/', views.HelpPageView.as_view(), name='help_page'),
    path('rules/', views.RulesPageView.as_view(), name='rules_and_regulations'),
    path('upgrade_instructions/', views.UpgradeBalanceInstructionsView.as_view(), name='upgrade_instructions'),
]
