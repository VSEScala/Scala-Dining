from django.urls import path

from creditmanagement.views import (
    TransactionAddView,
    TransactionCSVView,
    TransactionListView,
)

app_name = "credits"

urlpatterns = [
    path("transactions/", TransactionListView.as_view(), name="transaction_list"),
    path("transactions/add/", TransactionAddView.as_view(), name="transaction_add"),
    path("transactions/csv/", TransactionCSVView.as_view(), name="transaction_csv"),
]
