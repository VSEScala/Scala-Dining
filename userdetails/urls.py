from allauth.account.views import LoginView
from django.urls import include, path

from userdetails.views import (
    DiningClaimHistoryView,
    DiningJoinHistoryView,
    PeopleAutocompleteView,
    RegisterView,
)
from userdetails.views_association import (
    AssociationOverview,
    AssociationSettingsView,
    AssociationTransactionAddView,
    AssociationTransactionListView,
    AutoCreateNegativeCreditsView,
    MembersEditView,
    MembersOverview,
    SiteCreditDetailView,
    SiteCreditView,
    SiteTransactionView,
)
from userdetails.views_user_settings import SettingsProfileView

urlpatterns = [
    path(
        "association/<slug:slug>/",
        include(
            [
                path("", AssociationOverview.as_view(), name="association_overview"),
                path(
                    "transactions/",
                    include(
                        [
                            path(
                                "",
                                AssociationTransactionListView.as_view(),
                                name="association_credits",
                            ),
                            path(
                                "process_negatives/",
                                AutoCreateNegativeCreditsView.as_view(),
                                name="association_process_negatives",
                            ),
                            path(
                                "add/",
                                AssociationTransactionAddView.as_view(),
                                name="association_transaction_add",
                            ),
                        ]
                    ),
                ),
                path("members/", MembersOverview.as_view(), name="association_members"),
                path(
                    "members/edit/",
                    MembersEditView.as_view(),
                    name="association_members_edit",
                ),
                path(
                    "settings/",
                    AssociationSettingsView.as_view(),
                    name="association_settings",
                ),
                path(
                    "site_stats/",
                    include(
                        [
                            path(
                                "credit/",
                                SiteCreditView.as_view(),
                                name="association_site_credit_stats",
                            ),
                            path(
                                "credit/add/",
                                SiteTransactionView.as_view(),
                                name="association_site_transaction_add",
                            ),
                            path(
                                "credit/account/<int:pk>/",
                                SiteCreditDetailView.as_view(),
                                name="association_site_credit_detail",
                            ),
                        ]
                    ),
                ),
            ]
        ),
    ),
    path(
        "statistics/",
        include(
            [
                path("joined/", DiningJoinHistoryView.as_view(), name="history_lists"),
                path(
                    "joined/<int:page>/",
                    DiningJoinHistoryView.as_view(),
                    name="history_lists",
                ),
                path(
                    "claimed/",
                    DiningClaimHistoryView.as_view(),
                    name="history_claimed_lists",
                ),
                path(
                    "claimed/<int:page>/",
                    DiningClaimHistoryView.as_view(),
                    name="history_claimed_lists",
                ),
            ]
        ),
    ),
    path("settings/", SettingsProfileView.as_view(), name="settings_account"),
    # Override allauth login and sign up page with our registration page
    path("login/", LoginView.as_view(), name="account_login"),
    path("signup/", RegisterView.as_view(), name="account_signup"),
    path(
        "people-autocomplete/",
        PeopleAutocompleteView.as_view(),
        name="people_autocomplete",
    ),
]
