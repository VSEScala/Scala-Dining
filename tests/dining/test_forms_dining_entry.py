from datetime import date

from django.test import TestCase

from Dining.forms import DiningEntryCreateForm
from UserDetails.models import User
from tests.dining.helpers import create_dining_list


class DiningEntryCreateFormTestCase(TestCase):

    def test_form(self):
        # Todo: test creation
        pass

    def test_dining_list_closed(self):
        user = User.objects.create_user('noortje')
        dl = create_dining_list(date=date(2018, 1, 1))
        form = DiningEntryCreateForm(user, dl, {})
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('dining_list', 'closed'))

    def test_dining_list_no_room(self):
        user = User.objects.create_user('noortje')
        # Choosing a date far in the future so that the dining list is open
        # Could also patch timezone.now using unittest.mock
        dl = create_dining_list(date=date(2100, 1, 1), max_diners=0)
        form = DiningEntryCreateForm(user, dl, {})
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('dining_list', 'full'))

    def test_race_condition_max_diners(self):
        user1 = User.objects.create_user('noortje')
        user2 = User.objects.create_user('ankie')
        # Choosing a date far in the future so that the dining list is open
        # Could also patch timezone.now using unittest.mock
        list = create_dining_list(date=date(2100, 1, 1), max_diners=1)

        # Create first entry
        entry1form = DiningEntryCreateForm(user1, list, {})
        entry1valid = entry1form.is_valid()
        print(entry1form.errors)
        # Try creating next entry without saving first entry
        entry2form = DiningEntryCreateForm(user2, list, {})
        # Todo: this should throw an exception or block
        entry2valid = entry2form.is_valid()

        # Assert something like:
        self.assertTrue(entry1valid)
        self.assertFalse(entry2valid)

    def test_race_condition_double_entry(self):
        # Todo, similar as above
        pass
