from django.urls import path
from . import views_association
from CreditManagement.views import TransactionAddView


urlpatterns = [
    path('transactions', views_association.CreditsOverview.as_view(), name='association_credits'),
    path('transactions/<int:page>', views_association.CreditsOverview.as_view(), name='association_credits'),
    path('transactions/add', TransactionAddView.as_view(), name='transaction_add'),
    path('members', views_association.MembersOverview.as_view(), name='association_members'),
    path('members/<int:page>', views_association.MembersOverview.as_view(), name='association_members'),
    path('members/edit', views_association.MembersEditView.as_view(), name='association_members_edit'),
    path('members/edit/<int:page>', views_association.MembersEditView.as_view(), name='association_members_edit'),

]
