from allauth.socialaccount.providers.base import AuthAction, ProviderAccount
from django.templatetags.static import static

from allauthproviders.base import AssociationProvider


class QuadriviumAccount(ProviderAccount):
    def to_str(self):
        # String that is displayed e.g. on the linked accounts page
        data = self.account.extra_data
        first_name = data.get("given_name")
        last_name = data.get("family_name")
        username = data.get("preferred_username")
        if not first_name or not last_name or not username:
            return super().to_str()
        return "{} {} ({})".format(first_name, last_name, username)


class QuadriviumProvider(AssociationProvider):
    id = "quadrivium"
    name = "ESMG Quadrivium"
    account_class = QuadriviumAccount

    logo = static("images/allauthproviders/quadrivium.svg")

    def get_scope(self, request):
        return ["openid", "email"]

    def get_auth_params(self, request, action):
        # Don't know what this does, but I'll leave it in case it does something
        ret = super().get_auth_params(request, action)
        if action == AuthAction.REAUTHENTICATE:
            ret["prompt"] = "select_account"
        return ret

    def extract_uid(self, data):
        return str(data["sub"])

    def extract_common_fields(self, data):
        return dict(
            username=data.get("preferred_username", data.get("given_name")),
            email=data.get("email"),
            first_name=data.get("given_name"),
            last_name=data.get("family_name"),
        )


provider_classes = [QuadriviumProvider]
