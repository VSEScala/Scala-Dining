from allauth.socialaccount.providers.oauth2.provider import OAuth2Provider


class AssociationProvider(OAuth2Provider):
    """Extension of the allauth provider to add app specific functionality for association handling."""

    # Url for association logo for display
    logo = None
