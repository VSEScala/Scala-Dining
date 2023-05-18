from allauth.socialaccount.models import SocialAccount, SocialApp
from django.contrib.sites.models import Site
from django.test import TestCase

from userdetails.externalaccounts import _create_membership
from userdetails.models import Association, User, UserMembership


class CreateMembershipTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ankie", "ankie@cats.cat")
        self.social_app = SocialApp.objects.create(
            provider="quadrivium", name="ESMG Quadrivium"
        )
        self.social_app.sites.add(
            Site.objects.first()
        )  # Allauth needs a link to a Site
        self.social_account = SocialAccount.objects.create(
            user=self.user, provider="quadrivium"
        )
        self.association = Association.objects.create(
            name="Q", slug="q", social_app=self.social_app
        )
        self.association_not_linked = Association.objects.create(name="R", slug="r")

    def test_create_membership(self):
        _create_membership(self.social_account, None)
        self.assertTrue(self.user.is_verified_member_of(self.association))
        self.assertFalse(self.user.is_verified_member_of(self.association_not_linked))

    def test_verify(self):
        # Create unverified
        membership = UserMembership.objects.create(
            related_user=self.user, association=self.association
        )
        _create_membership(self.social_account, None)
        membership.refresh_from_db()
        self.assertTrue(membership.is_verified)

    def test_no_linked_associations(self):
        self.association.social_app = None
        self.association.save()
        with self.assertWarns(UserWarning):
            _create_membership(self.social_account, None)
