from django.urls import path

from CreditManagement.views import TransactionAddView
from .views_association import CreditsOverview, MembersOverview, MembersEditView, TransactionsCsvView

urlpatterns = [
    path('transactions/', CreditsOverview.as_view(), name='association_credits'),
    path('transactions/csv/', TransactionsCsvView.as_view(), name='association_transactions_csv'),
    path('transactions/add/', TransactionAddView.as_view(), name='transaction_add'),
    path('members/', MembersOverview.as_view(), name='association_members'),
    path('members/edit/', MembersEditView.as_view(), name='association_members_edit'),
]
