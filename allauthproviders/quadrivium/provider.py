from allauth.account.models import EmailAddress
from allauth.socialaccount import app_settings
from allauth.socialaccount.providers.base import AuthAction, ProviderAccount
from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider
from django.templatetags.static import static


class Scope:
    EMAIL = 'email'
    PROFILE = 'profile'
    PHONE = 'phone'
    ADDRESS = 'address'


# IDENTITY_CLAIMS = frozenset([
#     'sub', 'name', 'given_name', 'family_name', 'middle_name',
#     'nickname', 'preferred_username', 'profile', 'picture',
#     'website', 'email', 'email_verified', 'gender', 'birthdate',
#     'zoneinfo', 'locale', 'phone_number', 'phone_number_verified',
#     'address', 'updated_at', 'aq:location'
# ])


class QuadriviumAccount(ProviderAccount):
    # def get_profile_url(self):
    #     return self.account.extra_data.get('profile')
    #
    # def get_avatar_url(self):
    #     return self.account.extra_data.get('picture')


    def to_str(self):
        data = self.account.extra_data
        first_name = data.get('given_name')
        last_name = data.get('family_name')
        username = data.get('preferred_username')
        if not first_name or not last_name or not username:
            return super().to_str()
        return "{} {} ({})".format(first_name, last_name, username)


class QuadriviumProvider(OAuth2Provider):
    id = 'quadrivium'
    name = 'ESMG Quadrivium'
    account_class = QuadriviumAccount
    # Custom property not included in library
    logo = static('images/allauthproviders/quadrivium.svg')

    def get_scope(self, request):
        scope = set(super().get_scope(request))
        scope.add("openid")

        if Scope.EMAIL in scope:
            modifiers = ""
            if app_settings.EMAIL_REQUIRED:
                modifiers += "r"
            if app_settings.EMAIL_VERIFICATION:
                modifiers += "s"
            if modifiers:
                scope.add(Scope.EMAIL + "~" + modifiers)
                scope.remove(Scope.EMAIL)
        return list(scope)

    def get_default_scope(self):
        scope = []
        if app_settings.QUERY_EMAIL:
            scope.append(Scope.EMAIL)
        return scope

    def get_auth_params(self, request, action):
        ret = super().get_auth_params(request, action)
        if action == AuthAction.REAUTHENTICATE:
            ret['prompt'] = 'select_account'
        return ret

    def extract_uid(self, data):
        return str(data['sub'])

    def extract_common_fields(self, data):
        return dict(
            username=data.get('preferred_username', data.get('given_name')),
            email=data.get('email'),
            first_name=data.get('given_name'),
            last_name=data.get('family_name')
        )

    # def extract_extra_data(self, data):
    #     return {k: v for k, v in data.items() if k in IDENTITY_CLAIMS}

    def extract_email_addresses(self, data):
        ret = []
        email = data.get('email')
        if email and data.get('email_verified'):
            ret.append(EmailAddress(email=email, verified=True, primary=True))
        return ret


provider_classes = [QuadriviumProvider]