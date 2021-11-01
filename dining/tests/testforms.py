from datetime import time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from creditmanagement.models import Transaction
from dining.forms import CreateSlotForm
from dining.models import DiningList
from userdetails.models import Association, User, UserMembership


class CreateSlotFormTestCase(TestCase):
    def setUp(self):
        self.association1 = Association.objects.create(name="Quadrivium")
        self.user1 = User.objects.create_user('jan')
        UserMembership.objects.create(related_user=self.user1, association=self.association1, verified_state=True)
        # Date two days in the future
        self.dining_date = timezone.now().date() + timedelta(days=2)
        self.form_data = {'dish': 'Kwark', 'association': str(self.association1.pk), 'max_diners': '18',
                          'serve_time': '17:00'}
        self.dining_list = DiningList(date=self.dining_date)
        self.form = CreateSlotForm(self.user1, self.form_data, instance=self.dining_list)

    def test_creation(self):
        self.assertTrue(self.form.is_valid())
        dining_list = self.form.save()
        dining_list.refresh_from_db()

        # Assert
        self.assertEqual('Kwark', dining_list.dish)
        self.assertEqual(self.association1, dining_list.association)
        self.assertEqual(18, dining_list.max_diners)
        self.assertEqual(time(17, 00), dining_list.serve_time)
        self.assertEqual(self.dining_date, dining_list.date)

    def test_invalid_association(self):
        """Tests using an association which the user is not a member of.

        NOTE: when there is 1 available association, the form sets the association field to disabled. This means that
        the value that is sent with the form is totally ignored in favor of the initial value of the field. Therefore
        setting a different invalid association in the form data results in the form data actually being valid, but it
        does not use this association, instead it uses the other association which the user is actually a member of.

        Source: https://docs.djangoproject.com/en/2.2/ref/forms/fields/#disabled
        """
        association = Association.objects.create(name='Knights')
        form_data = {'dish': 'Boter', 'association': str(association.pk), 'max_diners': '20',
                     'serve_time': '18:00'}
        form = CreateSlotForm(self.user1, form_data, instance=DiningList(date=self.dining_date))
        self.assertTrue(form.is_valid())
        # Check that the actual association is not Knights but Quadrivium
        self.assertEqual(self.association1, form.instance.association)

    def test_association_unique_for_date(self):
        """Tests that there can be only one dining slot for an association for each date."""
        # Save one dining list
        self.form.save()

        # Try creating another one with same association
        dl = DiningList(date=self.dining_date)
        data = {'dish': 'Kwark', 'association': str(self.association1.pk), 'max_diners': '18',
                'serve_time': '17:00'}
        form = CreateSlotForm(self.user1, data, instance=dl)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('association'))

    def test_insufficient_balance(self):
        Transaction.objects.create(source=self.user1.account,
                                   target=self.association1.account,
                                   amount=Decimal('99'),
                                   created_by=self.user1)
        self.assertFalse(self.form.is_valid())

    def test_serve_time_too_late(self):
        # Actually tests a different class, but put here for convenience, to test it via the CreateSlotForm class
        self.form_data['serve_time'] = '23:30'
        self.assertFalse(self.form.is_valid())

    def test_serve_time_too_early(self):
        # Actually tests a different class, but put here for convenience, to test it via the CreateSlotForm class
        self.form_data['serve_time'] = '11:00'
        self.assertFalse(self.form.is_valid())
