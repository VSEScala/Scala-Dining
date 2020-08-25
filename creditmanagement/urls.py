from django.urls import path

from creditmanagement.views import TransactionListView, TransactionAddView, MoneyObtainmentView, TransactionCSVView

app_name = 'credits'

urlpatterns = [
    path('transactions/', TransactionListView.as_view(), name='transaction_list'),
    path('transactions/add/', TransactionAddView.as_view(), name='transaction_add'),
    path('transactions/csv/', TransactionCSVView.as_view(), name='transaction_csv'),
    path('dining_money/', MoneyObtainmentView.as_view(), name='dining_money')
]
