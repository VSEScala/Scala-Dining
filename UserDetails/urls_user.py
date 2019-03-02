from django.urls import path
from . import views_user


urlpatterns = [
    path('history/dining/', views_user.DiningHistoryView.as_view(), name='history_lists'),
    path('history/dining/<int:page>/', views_user.DiningHistoryView.as_view(), name='history_lists'),
    path('settings/', views_user.SettingViewEssentials.as_view(), name='settings_essential'),
    path('settings/dining/', views_user.SettingViewDining.as_view(), name='settings_dining'),
]
