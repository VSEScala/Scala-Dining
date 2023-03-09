from datetime import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from userdetails.models import Association, User, UserMembership


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

    def test_username_case_insensitive(self):
        """Cleaning should raise ValidationError for an existing username with different case."""
        with self.assertRaises(ValidationError) as cm:
            User(username='Noortje').full_clean()
        exception = cm.exception
        self.assertEqual(exception.error_dict['username'][0].code, 'unique')


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

    def test_set_pending(self):
        membership = UserMembership.objects.create(
            related_user=self.user,
            association=self.association,
            is_verified=True,
            verified_on=datetime(2020, 2, 1, tzinfo=timezone.utc),
        )
        self.assertIs(membership.get_verified_state(), True)
        membership.set_pending()
        self.assertIs(membership.get_verified_state(), None)

    def test_is_frozen(self):
        membership = UserMembership.objects.create(
            related_user=self.user,
            association=self.association,
            is_verified=True,
            verified_on=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        self.assertFalse(membership.is_frozen())
        membership.verified_on = timezone.now()
        self.assertTrue(membership.is_frozen())

    def test_is_rejected(self):
        membership = UserMembership.objects.create(
            related_user=self.user,
            association=self.association,
        )
        self.assertFalse(membership.is_rejected())
        membership = UserMembership.objects.create(
            related_user=self.user,
            association=self.association,
            is_verified=True,
            verified_on=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        self.assertFalse(membership.is_rejected())
        membership.is_verified = False
        self.assertTrue(membership.is_rejected())

    def test_is_pending(self):
        membership = UserMembership.objects.create(
            related_user=self.user,
            association=self.association,
        )
        self.assertTrue(membership.is_pending())
        membership.set_verified(True)
        self.assertFalse(membership.is_pending())
