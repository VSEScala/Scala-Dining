from django.urls import path, include
from allauth.account.views import LoginView

from CreditManagement.views import TransactionAddView
from .views import RegisterView, DiningJoinHistoryView, DiningClaimHistoryView, PeopleAutocompleteView
from .views_user_settings import SettingsProfileView
from .views_association import CreditsOverview, TransactionsCsvView, MembersOverview, MembersEditView, \
    AssociationOverview, AssociationSettingsView, AutoCreateNegativeCreditsView

urlpatterns = [
    path('association/<slug:association_name>/', include([
        path('', AssociationOverview.as_view(), name='association_overview'),
        path('transactions/', include([
            path('', CreditsOverview.as_view(), name='association_credits'),
            path('process_negatives/', AutoCreateNegativeCreditsView.as_view(), name='association_process_negatives'),
            path('csv/', TransactionsCsvView.as_view(), name='association_transactions_csv'),
            path('add/', TransactionAddView.as_view(), name='transaction_add'),
        ])),
        path('members/', MembersOverview.as_view(), name='association_members'),
        path('members/edit/', MembersEditView.as_view(), name='association_members_edit'),
        path('settings/', AssociationSettingsView.as_view(), name='association_settings')
    ])),

    path('statistics/', include([
        path('joined/', DiningJoinHistoryView.as_view(), name='history_lists'),
        path('joined/<int:page>/', DiningJoinHistoryView.as_view(), name='history_lists'),
        path('claimed/', DiningClaimHistoryView.as_view(), name='history_claimed_lists'),
        path('claimed/<int:page>/', DiningClaimHistoryView.as_view(), name='history_claimed_lists'),
    ])),


    path('settings/', SettingsProfileView.as_view(), name='settings_account'),

    # Override allauth login and sign up page with our registration page
    path('login/', LoginView.as_view(), name='account_login'),
    path('signup/', RegisterView.as_view(), name='account_signup'),

    path('people-autocomplete/', PeopleAutocompleteView.as_view(), name='people_autocomplete'),

]
