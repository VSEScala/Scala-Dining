from datetime import date, datetime, time
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import NON_FIELD_ERRORS

from CreditManagement.models import FixedTransaction
from Dining.forms import DiningEntryUserCreateForm, DiningEntryDeleteForm, DiningEntryExternalCreateForm
from Dining.models import DiningEntry, DiningList, DiningEntryUser, DiningEntryExternal
from UserDetails.models import User, Association, UserMembership


def _create_dining_list(**kwargs):
    """
    Creates a dining list with defaults if omitted.
    """
    if 'association' not in kwargs:
        kwargs['association'] = Association.objects.create()
    if 'date' not in kwargs:
        kwargs['date'] = date(2018, 1, 4)
    if 'sign_up_deadline' not in kwargs:
        kwargs['sign_up_deadline'] = datetime.combine(kwargs['date'], time(17, 00))
    if 'claimed_by' not in kwargs:
        kwargs['claimed_by'] = User.objects.create_user('tessa', 'tessa@punt.nl')
    return DiningList.objects.create(**kwargs)


class DiningEntryUserCreateFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.association = Association.objects.create()
        cls.user = User.objects.create_user('jan')
        cls.user2 = User.objects.create_user('noortje', email='noortje@cat.cat')

    def setUp(self):
        # Not in setUpTestData to ensure that it is fresh for every test case
        self.dining_list = DiningList.objects.create(date=date(2089, 1, 1), association=self.association,
                                                     claimed_by=self.user,
                                                     sign_up_deadline=datetime(2088, 1, 1, tzinfo=timezone.utc))
        self.dining_entry = DiningEntryUser(dining_list=self.dining_list, user=self.user2, created_by=self.user2)
        self.post_data = {'user': str(self.user2.pk)}

    def test_form(self):
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertTrue(form.is_valid())

    def test_dining_list_not_adjustable(self):
        self.dining_list.date = date(2000, 1, 2)
        self.dining_list.sign_up_deadline = datetime(2000, 1, 1, tzinfo=timezone.utc)
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'closed'))

    def test_dining_list_closed(self):
        self.dining_list.sign_up_deadline = datetime(2000, 1, 1, tzinfo=timezone.utc)  # Close list
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'closed'))

    def test_dining_list_closed_owner(self):
        """Closed exception for list owner"""
        self.dining_list.sign_up_deadline = datetime(2000, 1, 1, tzinfo=timezone.utc)  # Close list
        self.dining_entry.created_by = self.user  # Entry creator is dining list owner
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertTrue(form.is_valid())

    def test_dining_list_no_room(self):
        self.dining_list.max_diners = 0
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'full'))

    def test_dining_list_no_room_owner(self):
        self.dining_list.max_diners = 0
        self.dining_entry.created_by = self.user  # Entry creator is dining list owner
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertTrue(form.is_valid())

    def test_race_condition_max_diners(self):
        """Note! As long as this test passes, the race condition is present! Ideally therefore you'd want this test case
        to fail."""
        self.dining_list.max_diners = 1

        # Create first entry
        entry1form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        entry1valid = entry1form.is_valid()
        # Try creating next entry without saving first entry
        entry2form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        entry2valid = entry2form.is_valid()

        # Both entries are valid which means that both entries will be created, while max_diners==1
        # This also means that a duplicate entry is created for the user
        self.assertTrue(entry1valid)
        self.assertTrue(entry2valid)

    def test_limited_to_association_is_member(self):
        self.dining_list.limit_signups_to_association_only = True
        UserMembership.objects.create(related_user=self.user2, association=self.association,
                                      is_verified=True, verified_on=timezone.now())
        self.assertTrue(DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry).is_valid())

    def test_limited_to_association_is_not_member(self):
        self.dining_list.limit_signups_to_association_only = True
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'members_only'))

    def test_balance_too_low(self):
        FixedTransaction.objects.create(source_user=self.user2, amount=Decimal('99'))
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'nomoneyzz'))

    def test_balance_too_low_exception(self):
        # Make user member of association with exception
        assoc = Association.objects.create(slug='ankie4president', name='PvdD', has_min_exception=True)
        UserMembership.objects.create(related_user=self.user2, association=assoc, is_verified=True,
                                      verified_on=timezone.now())
        FixedTransaction.objects.create(source_user=self.user2, amount=Decimal('99'))
        form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)
        self.assertTrue(form.is_valid())


class DiningEntryExternalCreateFormTestCase(TestCase):
    """Only test a valid form instance since the clean method has been tested above already"""

    @classmethod
    def setUpTestData(cls):
        cls.association = Association.objects.create()
        cls.user = User.objects.create_user('jan')
        cls.user2 = User.objects.create_user('noortje', email='noortje@cat.cat')

    def setUp(self):
        # Not in setUpTestData to ensure that it is fresh for every test case
        self.dining_list = DiningList.objects.create(date=date(2089, 1, 1), association=self.association,
                                                     claimed_by=self.user,
                                                     sign_up_deadline=datetime(2088, 1, 1, tzinfo=timezone.utc))
        self.dining_entry = DiningEntryExternal(dining_list=self.dining_list, user=self.user2, created_by=self.user2)
        self.post_data = {'name': 'Ankie'}

    def test_form(self):
        form = DiningEntryExternalCreateForm(self.post_data, instance=self.dining_entry)
        self.assertTrue(form.is_valid())


class DiningEntryDeleteFormTestCase(TestCase):

    def test_remove_on_close(self):
        # Setup
        user1 = User.objects.create_user('noortje', email="noortje@universe.cat")
        user2 = User.objects.create_user('ankie', email="ankie@universe.cat")
        dl = _create_dining_list(date=date(2100, 1, 1), claimed_by=user1)
        e1 = DiningEntry.objects.create(user=user1, created_by=user1, dining_list=dl)
        e2 = DiningEntry.objects.create(user=user2, created_by=user2, dining_list=dl)

        # Set the new date in the past
        dl.sign_up_deadline = timezone.now()
        dl.save()

        # Check user deletion forms
        # Claimer can delete user
        form = DiningEntryDeleteForm(user1, e1)
        self.assertTrue(form.is_valid())
        # Others can not delete themselves
        form = DiningEntryDeleteForm(user2, e2)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'closed'))
