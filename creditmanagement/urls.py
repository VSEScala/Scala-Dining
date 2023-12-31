from django.urls import include, path

from creditmanagement.views import (
    TransactionAddView,
    TransactionCSVView,
    TransactionListView,
)

app_name = "credits"

urlpatterns = [
    path(
        "transactions/",
        include(
            [
                path("", TransactionListView.as_view(), name="transaction_list"),
                path("add/", TransactionAddView.as_view(), name="transaction_add"),
                path(
                    "csv/<int:pk>/",
                    TransactionCSVView.as_view(),
                    name="transaction_csv",
                ),
            ]
        ),
    ),
]
