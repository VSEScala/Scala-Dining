import requests
from allauth.socialaccount.providers.oauth2.views import (
    OAuth2Adapter,
    OAuth2CallbackView,
    OAuth2LoginView,
)

from .provider import QuadriviumProvider


class QuadriviumOAuth2Adapter(OAuth2Adapter):
    provider_id = QuadriviumProvider.id

    access_token_url = "https://keycloak2.esmgquadrivium.nl/auth/realms/q/protocol/openid-connect/token"
    authorize_url = (
        "https://keycloak2.esmgquadrivium.nl/auth/realms/q/protocol/openid-connect/auth"
    )
    profile_url = "https://keycloak2.esmgquadrivium.nl/auth/realms/q/protocol/openid-connect/userinfo"

    def complete_login(self, request, app, token, **kwargs):
        auth = {"Authorization": "Bearer " + token.token}
        resp = requests.get(self.profile_url, headers=auth)
        resp.raise_for_status()
        extra_data = resp.json()
        login = self.get_provider().sociallogin_from_response(request, extra_data)
        return login


oauth2_login = OAuth2LoginView.adapter_view(QuadriviumOAuth2Adapter)
oauth2_callback = OAuth2CallbackView.adapter_view(QuadriviumOAuth2Adapter)
