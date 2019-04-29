from allauth.account.signals import user_signed_up
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.signals import social_account_added
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone

from UserDetails.models import Association, UserMembership


def _create_membership(socialaccount):
    user = socialaccount.user
    association_slug = socialaccount.get_provider().association_slug
    association = Association.objects.get(slug=association_slug)
    membership = UserMembership.objects.filter(related_user=user, association=association).first()
    if membership:
        # There exists a membership already, verify it if needed
        if not membership.is_verified:
            membership.is_verified = True
            membership.verified_on = timezone.now()
            membership.save()
    else:
        UserMembership.objects.create(related_user=user, association=association, is_verified=True,
                                      verified_on=timezone.now())


@receiver(user_signed_up)
def automatic_association_link(sender, request, user, **kwargs):
    """Create membership when someone signs up using an association account"""
    sociallogin = kwargs.get('sociallogin', None)
    if not sociallogin:
        # Normal registration, not using association account
        return
    _create_membership(sociallogin.account)


@receiver(social_account_added)
def automatic_association_link2(sender, request, sociallogin, **kwargs):
    """Create membership status when someone connects an association account to an existing dining account"""
    _create_membership(sociallogin.account)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter that redirects user to settings page after first login using external account, so that she directly sees
    the option of settings any allergies/dietary wishes."""

    def save_user(self, request, sociallogin, form=None):
        u = super().save_user(request, sociallogin, form)
        sociallogin.state['next'] = reverse('settings_account')
        return u
