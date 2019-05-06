from datetime import date

from django.core.exceptions import NON_FIELD_ERRORS
from django.test import TestCase

from Dining.forms import DiningEntryUserCreateForm
from Dining.models import DiningList
from UserDetails.models import User, Association


def _create_dining_list(**kwargs):
    """
    Creates a dining list with default date and association if omitted.
    """
    if not 'association' in kwargs:
        kwargs['association'] = Association.objects.create()
    if not 'date' in kwargs:
        kwargs['date'] = date(2018, 1, 4)
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
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'closed'))

    def test_dining_list_no_room(self):
        user = User.objects.create_user('noortje')
        # Choosing a date far in the future so that the dining list is open
        # Could also patch timezone.now using unittest.mock
        dl = _create_dining_list(date=date(2100, 1, 1), max_diners=0)
        form = DiningEntryUserCreateForm(user, dl, {})
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error(NON_FIELD_ERRORS, 'full'))

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
