from allauth.account.views import LoginView
from django.urls import path, include

from userdetails import views
from userdetails.views_association import AssociationTransactionListView, AssociationTransactionsCSVView, \
    MembersOverview, \
    MembersEditView, AssociationOverview, AssociationSettingsView, SiteDiningView, SiteCreditView, \
    AssociationTransactionAddView, SiteTransactionView, SiteCreditDetailView

urlpatterns = [
    path('association/<slug:association_name>/', include([
        path('', AssociationOverview.as_view(), name='association_overview'),
        path('transactions/', include([
            path('', AssociationTransactionListView.as_view(), name='association_credits'),
            path('csv/', AssociationTransactionsCSVView.as_view(), name='association_transactions_csv'),
            path('add/', AssociationTransactionAddView.as_view(), name='association_transaction_add'),
        ])),
        path('members/', MembersOverview.as_view(), name='association_members'),
        path('members/edit/', MembersEditView.as_view(), name='association_members_edit'),
        path('settings/', AssociationSettingsView.as_view(), name='association_settings'),
        path('site_stats/', include([
            path('dining/', SiteDiningView.as_view(), name='association_site_dining_stats'),
            path('credit/', SiteCreditView.as_view(), name='association_site_credit_stats'),
            path('credit/add/', SiteTransactionView.as_view(), name='association_site_transaction_add'),
            path('credit/account/<slug:slug>/', SiteCreditDetailView.as_view(), name='association_site_credit_detail'),
        ])),
    ])),

    path('statistics/', include([
        path('joined/', views.DiningJoinHistoryView.as_view(), name='history_lists'),
        path('claimed/', views.DiningClaimHistoryView.as_view(), name='history_claimed_lists'),
    ])),

    path('settings/', views.SettingsProfileView.as_view(), name='settings_account'),

    # Override allauth login and sign up page with our registration page
    path('login/', LoginView.as_view(), name='account_login'),
    path('signup/', views.RegisterView.as_view(), name='account_signup'),

    path('people-autocomplete/', views.PeopleAutocompleteView.as_view(), name='people_autocomplete'),

]
