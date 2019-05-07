from datetime import date, datetime, time
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import NON_FIELD_ERRORS

from Dining.forms import DiningEntryUserCreateForm, DiningEntryDeleteForm
from Dining.models import DiningEntry, DiningList
from UserDetails.models import User, Association


def _create_dining_list(**kwargs):
    """
    Creates a dining list with defaults if omitted.
    """
    if 'association' not in kwargs:
        kwargs['association'] = Association.objects.create()
    if 'date' not in kwargs:
        kwargs['date'] = date(2018, 1, 4)
    if 'sign_up_deadline' not in kwargs:
        kwargs['sign_up_deadline'] = datetime.combine(kwargs['date'], time(17,00))
    if 'claimed_by' not in kwargs:
        kwargs['claimed_by'] = User.objects.create_user('tessa', 'tessa@punt.nl')
    return DiningList.objects.create(**kwargs)


class DiningEntryCreateFormTestCase(TestCase):

    def test_form(self):
        # Todo: test creation
        pass

    def test_dining_list_closed(self):
        user = User.objects.create_user('noortje')
        dl = _create_dining_list(date=date(2018, 1, 1))
        form = DiningEntryUserCreateForm(user, dl, {})
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('dining_list', 'closed'))

    def test_dining_list_no_room(self):
        user = User.objects.create_user('noortje')
        # Choosing a date far in the future so that the dining list is open
        # Could also patch timezone.now using unittest.mock
        dl = _create_dining_list(date=date(2100, 1, 1), max_diners=0)
        form = DiningEntryUserCreateForm(user, dl, {})
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('dining_list', 'full'))

    def test_dining_list_no_room_owner(self):
        user = User.objects.create_user('noortje')
        # Choosing a date far in the future so that the dining list is open
        # Could also patch timezone.now using unittest.mock
        dl = _create_dining_list(date=date(2100, 1, 1), max_diners=0)
        # Make the claimer the owner
        dl.claimed_by = user
        dl.save()
        # Test if owner can now add someone
        form = DiningEntryUserCreateForm(user, dl, {})
        self.assertTrue(form.is_valid())

    def test_race_condition_max_diners(self):
        """Note! As long as this test passes, the race condition is present! Ideally therefore you'd want this test case
        to fail."""
        user1 = User.objects.create_user('noortje', email="noortje@universe.cat")
        user2 = User.objects.create_user('ankie', email="ankie@universe.cat")
        # Choosing a date far in the future so that the dining list is open
        # Could also patch timezone.now using unittest.mock
        list = _create_dining_list(date=date(2100, 1, 1), max_diners=1)

        # Create first entry
        entry1form = DiningEntryUserCreateForm(user1, list, {})
        entry1valid = entry1form.is_valid()
        # Try creating next entry without saving first entry
        entry2form = DiningEntryUserCreateForm(user2, list, {})
        entry2valid = entry2form.is_valid()

        # Both entries are valid which means that both entries will be created, while max_diners==1
        self.assertTrue(entry1valid)
        self.assertTrue(entry2valid)


class DiningEntryDeleteFormTestCase(TestCase):

    def test_remove_on_close(self):
        # Setup
        user1 = User.objects.create_user('noortje', email="noortje@universe.cat")
        user2 = User.objects.create_user('ankie', email="ankie@universe.cat")
        dl = _create_dining_list(date=date(2100, 1, 1), claimed_by=user1)
        e1 = DiningEntry.objects.create(user=user1, dining_list=dl)
        e2 = DiningEntry.objects.create(user=user2, dining_list=dl)

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
