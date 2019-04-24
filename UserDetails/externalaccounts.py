from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.signals import social_account_added
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from UserDetails.models import Association, UserMembership


# Utilities for handling external association accounts

@receiver(social_account_added)
def automatic_association_link(sender, request, sociallogin):
    """Create or update association membership status when someone connects an association account"""

    # User should have been saved at this point
    user = sociallogin.account.user
    association_slug = sociallogin.account.provider.association_slug
    association = Association.objects.get(slug=association_slug)
    membership = UserMembership.objects.filter(related_user=user, association=association).first()
    if membership:
        # Mark verified if not already
        if not membership.is_verified:
            membership.is_verified = True
            membership.verified_on = timezone.now()
            membership.save()
    else:
        # Create membership
        UserMembership.objects.create(related_user=user, association=association, is_verified=True,
                                      verified_on=timezone.now())


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter that redirects user to settings page after first login using external account, so that she directly sees
    the option of settings any allergies/dietary wishes."""

    def get_connect_redirect_url(self, request, socialaccount):
        # Check if user is new, only then redirect, hacky solution by looking if the user was recently created
        created_at = socialaccount.user.date_joined
        now = timezone.now()
        if abs(now - created_at).seconds < 10:
            return reverse('settings_account')
        return super().get_connect_redirect_url(request, socialaccount)
