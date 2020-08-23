from datetime import date, datetime, time
from decimal import Decimal

from django.core.exceptions import NON_FIELD_ERRORS
from django.test import TestCase
from django.utils import timezone

from creditmanagement.models import FixedTransaction
from dining.forms import DiningEntryUserCreateForm, DiningEntryDeleteForm, DiningEntryExternalCreateForm
from dining.models import DiningList, DiningEntryUser, DiningEntryExternal
from userdetails.models import User, Association, UserMembership


def _create_dining_list(**kwargs):
    """Creates a dining list with defaults if omitted."""
    if 'association' not in kwargs:
        kwargs['association'] = Association.objects.create()
    if 'date' not in kwargs:
        kwargs['date'] = date(2018, 1, 4)
    if 'sign_up_deadline' not in kwargs:
        kwargs['sign_up_deadline'] = datetime.combine(kwargs['date'], time(17, 00))
    dl = DiningList.objects.create(**kwargs)
    dl.owners.add(User.objects.create_user('tessa', 'tessa@punt.nl'))
    return dl


class DiningEntryUserCreateFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.association = Association.objects.create()
        cls.user = User.objects.create_user('jan')
        cls.user2 = User.objects.create_user('noortje', email='noortje@cat.cat')

    def setUp(self):
        # Not in setUpTestData to ensure that it is fresh for every test case
        self.dining_list = DiningList.objects.create(date=date(2089, 1, 1), association=self.association,
                                                     sign_up_deadline=datetime(2088, 1, 1, tzinfo=timezone.utc))
        self.dining_list.owners.add(self.user)
        self.dining_entry = DiningEntryUser(dining_list=self.dining_list, created_by=self.user2)
        self.post_data = {'user': str(self.user2.pk)}
        self.form = DiningEntryUserCreateForm(self.post_data, instance=self.dining_entry)

    def test_form(self):
        self.assertTrue(self.form.is_valid())

    def test_dining_list_not_adjustable(self):
        self.dining_list.date = date(2000, 1, 2)
        self.dining_list.sign_up_deadline = datetime(2000, 1, 1, tzinfo=timezone.utc)
        self.assertFalse(self.form.is_valid())
        self.assertTrue(self.form.has_error(NON_FIELD_ERRORS, 'closed'))

    def test_dining_list_closed(self):
        self.dining_list.sign_up_deadline = datetime(2000, 1, 1, tzinfo=timezone.utc)  # Close list
        self.assertFalse(self.form.is_valid())
        self.assertTrue(self.form.has_error(NON_FIELD_ERRORS, 'closed'))

    def test_dining_list_closed_owner(self):
        """Tests closed exception for list owner."""
        self.dining_list.sign_up_deadline = datetime(2000, 1, 1, tzinfo=timezone.utc)  # Close list
        self.dining_entry.created_by = self.user  # Entry creator is dining list owner
        self.assertTrue(self.form.is_valid())

    def test_dining_list_no_room(self):
        self.dining_list.max_diners = 0
        self.assertFalse(self.form.is_valid())
        self.assertTrue(self.form.has_error(NON_FIELD_ERRORS, 'full'))

    def test_dining_list_no_room_owner(self):
        self.dining_list.max_diners = 0
        self.dining_entry.created_by = self.user  # Entry creator is dining list owner
        self.assertTrue(self.form.is_valid())

    def test_race_condition_max_diners(self):
        """Tries to do a race condition on the maximum number of diners.

        Note! As long as this test passes, the race condition is present! Ideally therefore you'd want this test case
        to fail.
        """
        self.dining_list.max_diners = 1

        # Try creating 2 entries using race condition
        entry1 = DiningEntryUser(dining_list=self.dining_list, user=self.user2, created_by=self.user2)
        entry2 = DiningEntryUser(dining_list=self.dining_list, user=self.user2, created_by=self.user2)
        form1 = DiningEntryUserCreateForm(self.post_data, instance=entry1)
        form2 = DiningEntryUserCreateForm(self.post_data, instance=entry2)
        self.assertTrue(form1.is_valid())  # Both forms should be valid
        self.assertTrue(form2.is_valid())
        form1.save()  # Since they're both valid, they'll both get saved
        form2.save()
        # Now there are 2 entries of the same user and with max_diners being 1
        self.assertEqual(2, DiningEntryUser.objects.all().count())

    def test_limited_to_association_is_member(self):
        self.dining_list.limit_signups_to_association_only = True
        UserMembership.objects.create(related_user=self.user2, association=self.association,
                                      is_verified=True, verified_on=timezone.now())
        self.assertTrue(self.form.is_valid())

    def test_limited_to_association_is_not_member(self):
        self.dining_list.limit_signups_to_association_only = True
        self.assertFalse(self.form.is_valid())
        self.assertTrue(self.form.has_error(NON_FIELD_ERRORS, 'members_only'))

    def test_balance_too_low(self):
        FixedTransaction.objects.create(source_user=self.user2, amount=Decimal('99'))
        self.assertFalse(self.form.is_valid())
        self.assertTrue(self.form.has_error(NON_FIELD_ERRORS, 'nomoneyzz'))

    def test_balance_too_low_exception(self):
        # Make user member of association with exception
        assoc = Association.objects.create(slug='ankie4president', name='PvdD', has_min_exception=True)
        UserMembership.objects.create(related_user=self.user2, association=assoc, is_verified=True,
                                      verified_on=timezone.now())
        FixedTransaction.objects.create(source_user=self.user2, amount=Decimal('99'))
        self.assertTrue(self.form.is_valid())

    def test_invalid_user(self):
        self.post_data['user'] = '100'
        self.assertFalse(self.form.is_valid())


class DiningEntryExternalCreateFormTestCase(TestCase):
    """This class only tests a valid form instance since the clean method has been tested above already."""

    @classmethod
    def setUpTestData(cls):
        cls.association = Association.objects.create()
        cls.user = User.objects.create_user('jan')
        cls.user2 = User.objects.create_user('noortje', email='noortje@cat.cat')

    def setUp(self):
        # Not in setUpTestData to ensure that it is fresh for every test case
        self.dining_list = DiningList.objects.create(date=date(2089, 1, 1), association=self.association,
                                                     sign_up_deadline=datetime(2088, 1, 1, tzinfo=timezone.utc))
        self.dining_list.owners.add(self.user)
        self.dining_entry = DiningEntryExternal(dining_list=self.dining_list, user=self.user2, created_by=self.user2)
        self.post_data = {'name': 'Ankie'}

    def test_form(self):
        form = DiningEntryExternalCreateForm(self.post_data, instance=self.dining_entry)
        self.assertTrue(form.is_valid())


class DiningEntryDeleteFormTestCase(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user('ankie', email='ankie@universe.cat')
        self.user2 = User.objects.create_user('noortje', email='noortje@universe.cat')
        self.association = Association.objects.create(name='C&M')
        self.dining_list = DiningList.objects.create(date=date(2100, 1, 1), association=self.association,
                                                     sign_up_deadline=datetime(2100, 1, 1, tzinfo=timezone.utc))
        self.dining_list.owners.add(self.user1)
        self.entry = DiningEntryUser(user=self.user2, created_by=self.user2, dining_list=self.dining_list)
        self.form = DiningEntryDeleteForm(self.entry, self.user2, {})

    def test_valid(self):
        self.assertTrue(self.form.is_valid())

    def test_no_permission_invalid_user(self):
        self.entry.user = self.user1
        self.entry.created_by = self.user1
        self.assertFalse(self.form.is_valid())

    def test_no_permission_owner_exception(self):
        # User 1 is owner so should be able to remove user 2
        form = DiningEntryDeleteForm(self.entry, self.user1, {})
        self.assertTrue(form.is_valid())

    def test_no_permission_created_by_exception(self):
        # User is not equal to deleter but the deleter did create the entry
        self.entry.user = self.user1
        self.assertTrue(self.form.is_valid())

    def test_dining_list_closed(self):
        self.dining_list.sign_up_deadline = datetime(2001, 1, 1, tzinfo=timezone.utc)
        self.assertFalse(self.form.is_valid())

    def test_dining_list_closed_exception(self):
        self.dining_list.sign_up_deadline = datetime(2001, 1, 1, tzinfo=timezone.utc)
        form = DiningEntryDeleteForm(self.entry, self.user1, {})
        self.assertTrue(form.is_valid())

    def test_dining_list_not_adjustable(self):
        self.dining_list.date = date(2001, 1, 1)
        self.assertFalse(self.form.is_valid())
