from django.test import TestCase
from django.utils import timezone

from UserDetails.models import Association, User, UserMembership


class AssociationTestCase(TestCase):
    def setUp(self):
        self.association = Association.objects.create()

    def test_has_new_member_requests_false(self):
        self.assertFalse(self.association.has_new_member_requests())

    def test_has_new_member_requests_true(self):
        user = User.objects.create_user('ankie')
        UserMembership.objects.create(related_user=user, association=self.association)
        self.assertTrue(self.association.has_new_member_requests())


class UserTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('noortje')

    def test_has_min_balance_exception_no_membership(self):
        self.assertFalse(self.user.has_min_balance_exception())

    def test_has_min_balance_exception_false(self):
        association = Association.objects.create()
        UserMembership.objects.create(related_user=self.user, association=association, is_verified=True,
                                      verified_on=timezone.now())
        self.assertFalse(self.user.has_min_balance_exception())

    def test_has_min_balance_exception_true(self):
        association = Association.objects.create(has_min_exception=True)
        UserMembership.objects.create(related_user=self.user, association=association, is_verified=True,
                                      verified_on=timezone.now())
        self.assertTrue(self.user.has_min_balance_exception())

    def test_has_min_balance_exception_unverified_membership(self):
        association = Association.objects.create(has_min_exception=True)
        UserMembership.objects.create(related_user=self.user, association=association)
        self.assertFalse(self.user.has_min_balance_exception())


class UserMembershipTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('noortje')
        cls.association = Association.objects.create()

    def test_set_verified_true(self):
        membership = UserMembership.objects.create(related_user=self.user, association=self.association)
        self.assertIsNone(membership.get_verified_state())
        membership.set_verified(True)
        membership.refresh_from_db()  # To check if it's saved
        self.assertIs(membership.get_verified_state(), True)

    def test_set_verified_false(self):
        membership = UserMembership.objects.create(related_user=self.user, association=self.association)
        self.assertIsNone(membership.get_verified_state())
        membership.set_verified(False)
        membership.refresh_from_db()  # To check if it's saved
        self.assertIs(membership.get_verified_state(), False)
