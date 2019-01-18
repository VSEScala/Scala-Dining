from django.urls import path

from . import views
from .views import TransactionListView

app_name = 'credits'

urlpatterns = [
    path('transactions/', TransactionListView.as_view(), name='transaction_list'),
]