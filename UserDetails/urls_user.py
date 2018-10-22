from django.urls import path
from . import views_user


urlpatterns = [
    path('history/dining', views_user.DiningHistoryView.as_view(), name='history_lists'),
    path('history/dining/<int:page>', views_user.DiningHistoryView.as_view(), name='history_lists'),
    path('credits', views_user.CreditsOverview.as_view(), name='history_credits'),
    path('credits/<int:page>', views_user.CreditsOverview.as_view(), name='history_credits'),
    path('settings', views_user.SettingsView.as_view(), name='settings'),
    path('settings', views_user.SettingsView.as_view(), name='settings_personal'),
    path('settings', views_user.SettingsView.as_view(), name='settings_dining'),
]
