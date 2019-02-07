from django.conf import settings
from django.utils import timezone
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import User, UserMembership, Association


class QuadriviumOIDCAB(OIDCAuthenticationBackend):
    """Using the LDAP unique ID attribute and external_link field to link accounts between systems.

    # Todo: show allergies page after creation.
    """

    def create_user(self, claims):
        """For creating a new user, set full name, username and email and create membership."""
        username = claims.get('preferred_username')
        email = claims.get('email')
        first_name = claims.get('given_name')
        last_name = claims.get('family_name')
        ldap_id = claims.get('ldap_id')
        # Create user
        user = User.objects.create_user(username, email, first_name=first_name, last_name=last_name,
                                        external_link=ldap_id)
        # Create membership
        if settings.OIDC_ASSOCIATION_SLUG:
            association = Association.objects.get(slug=settings.OIDC_ASSOCIATION_SLUG)
            UserMembership.objects.create(related_user=user, association=association, is_verified=True,
                                          verified_on=timezone.now())
        return user

    def update_user(self, user, claims):
        # Todo: optionally update user details in the database when they have changed
        return super().update_user(user, claims)

    def filter_users_by_claims(self, claims):
        """This method searches for the user in the database, by using the LDAP ID."""
        ldap_id = claims.get('ldap_id')
        if not ldap_id:
            return User.objects.none()
        return User.objects.filter(external_link=ldap_id)
