from django.urls import path
from .views import *

app_name = 'credits'

urlpatterns = [
    path('transactions/', TransactionListView.as_view(), name='transaction_list'),
    path('transactions/transfer/', TransactionUserView.as_view(), name='transaction_transfer'),
    path('transactions/contribute/', DonationView.as_view(), name='transaction_donate'),
    path('transactions/delete/', TransactionDeleteView.as_view(), name='transaction_delete'),
    path('finalise_transactions/', TransactionFinalisationView.as_view(), name='transactions_finalise'),
    path('dining_money/', MoneyObtainmentView.as_view(), name='dining_money')
]