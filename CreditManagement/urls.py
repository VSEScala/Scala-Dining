from django.urls import path

from . import views
from .views import *

app_name = 'credits'

urlpatterns = [
    path('transactions/', TransactionListView.as_view(), name='transaction_list'),
    path('transactions/add', TransactionAddView.as_view(), name='transaction_add'),
    path('finalise_transactions', TransactionFinalisationView.as_view(), name='transactions_finalise')
]