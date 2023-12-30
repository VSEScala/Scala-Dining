from django.urls import path

from reports import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsView.as_view(), name="index"),
    path("balance/", views.BalanceView.as_view(), name="balance"),
    path("cashflow/", views.CashFlowIndexView.as_view(), name="cashflow_index"),
    path("cashflow/<int:pk>/", views.CashFlowView.as_view(), name="cashflow"),
    path("transactions/", views.TransactionsReportView.as_view(), name="transactions"),
    path("stale/", views.StaleAccountsView.as_view(), name="stale"),
]
