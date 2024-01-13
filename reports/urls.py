from django.urls import path

from reports import views

app_name = "reports"

urlpatterns = [
    path("", views.ReportsView.as_view(), name="index"),
    path("balance/", views.BalanceView.as_view(), name="balance"),
    path("cashflow/", views.CashFlowIndexView.as_view(), name="cashflow_index"),
    path("cashflow/<int:pk>/", views.CashFlowView.as_view(), name="cashflow"),
    path("cashflow2/", views.CashFlowMatrixView.as_view(), name="cashflow_matrix"),
    path("transactions/", views.TransactionsReportView.as_view(), name="transactions"),
    path("stale/", views.StaleAccountsView.as_view(), name="stale"),
    path("memberships/", views.MembershipCountView.as_view(), name="memberships"),
    path("diners/", views.DinersView.as_view(), name="diners"),
    path("leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
]
