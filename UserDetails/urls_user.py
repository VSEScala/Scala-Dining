from django.urls import path
from . import views_user


urlpatterns = [
    path('history/dining', views_user.DiningHistoryView.as_view(), name='history_lists'),
    path('history/dining/<int:page>', views_user.DiningHistoryView.as_view(), name='history_lists'),
    path('settings', views_user.SettingsView.as_view(), name='settings'),
    path('settings/essential', views_user.SettingView_Essentials.as_view(), name='settings_essential'),
    path('settings/dining', views_user.SettingView_Dining.as_view(), name='settings_dining'),
]
