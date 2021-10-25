from django.urls import path

from directdebit import views

urlpatterns = [
    path('upgrade/', views.UpgradeBalanceView.as_view(), name='upgrade-balance')
]
