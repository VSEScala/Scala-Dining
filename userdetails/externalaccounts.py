import warnings

from allauth.account.signals import user_signed_up
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.signals import social_account_added
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from userdetails.models import Association, UserMembership


def _create_membership(socialaccount, request):
    """Creates memberships for all associations that are linked to the external application."""
    user = socialaccount.user
    social_app = socialaccount.get_provider().get_app(request)
    linked_associations = Association.objects.filter(social_app=social_app)
    if not linked_associations:
        warnings.warn("No associations linked to the external account")
    for association in linked_associations:
        membership = UserMembership.objects.filter(
            related_user=user, association=association
        ).first()
        if membership:
            # There exists a membership already, verify it if needed
            if not membership.is_verified:
                membership.is_verified = True
                membership.verified_on = timezone.now()
                membership.save()
        else:
            UserMembership.objects.create(
                related_user=user,
                association=association,
                is_verified=True,
                verified_on=timezone.now(),
            )


@receiver(user_signed_up)
def automatic_association_link(sender, request, user, **kwargs):
    """Creates membership when someone signs up using an association account."""
    sociallogin = kwargs.get("sociallogin", None)
    if not sociallogin:
        # Normal registration, not using association account
        return
    _create_membership(sociallogin.account, request)


@receiver(social_account_added)
def automatic_association_link2(sender, request, sociallogin, **kwargs):
    """Creates membership status when someone connects an association account to an existing dining account."""
    _create_membership(sociallogin.account, request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter that redirects user to settings page after first login using external account.

    This is so that he directly sees the option of setting any allergies/dietary wishes.
    """

    def save_user(self, request, sociallogin, form=None):
        u = super().save_user(request, sociallogin, form)
        sociallogin.state["next"] = reverse("settings_account")
        return u
