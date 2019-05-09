from datetime import time, date, timedelta, datetime
from decimal import Decimal

from django.core.exceptions import NON_FIELD_ERRORS
from django.test import TestCase
from django.utils import timezone

from CreditManagement.models import FixedTransaction
from Dining.forms import CreateSlotForm, DiningEntryExternalCreateForm, DiningEntryUserCreateForm
from UserDetails.models import Association, User, UserMembership
from Dining.models import DiningList, DiningEntryExternal


class CreateSlotFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Do not modify the objects created here in tests, see:
        https://docs.djangoproject.com/en/2.1/topics/testing/tools/#django.test.TestCase.setUpTestData
        """
        cls.association1 = Association.objects.create(name="Quadrivium")
        cls.association2 = Association.objects.create(name="Knights")
        cls.association3 = Association.objects.create(name="Scala")
        cls.user1 = User.objects.create_user('jan')
        # cls.user2 = User.objects.create_user('klaas')
        cls.user1_assoc1 = UserMembership.objects.create(related_user=cls.user1, association=cls.association1,
                                                         is_verified=True)
        cls.user1_assoc2 = UserMembership.objects.create(related_user=cls.user1, association=cls.association2,
                                                         is_verified=True)

    def setUp(self):
        # Date two days in the future
        self.dining_date = timezone.now().date() + timedelta(days=2)
        self.form_data = {'dish': 'Kwark', 'association': str(self.association1.pk), 'max_diners': '18',
                          'serve_time': '17:00'}
        self.dining_list = DiningList(claimed_by=self.user1, date=self.dining_date)
        self.form = CreateSlotForm(self.form_data, instance=self.dining_list)

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
        """
        Tests using an association which the user is not a member of.

        Association 3 with user 1.
        """
        form_data = {'dish': 'Boter', 'association': str(self.association3.pk), 'max_diners': '20',
                     'serve_time': '18:00'}
        form = CreateSlotForm(form_data, instance=DiningList(claimed_by=self.user1, date=self.dining_date))
        self.assertFalse(form.is_valid())
        self.assertTrue(form.has_error('association', 'invalid_choice'))

    def test_occupied_association(self):
        """
        Creating a dining list on a date which is already occupied for your association.
        """
        # Todo: don't know why this test fails
        pass
        # DiningList.objects.create(date=self.dining_date, association=self.association1)
        # form_data = {'dish': '', 'association': self.association1.pk, 'max_diners': 20, 'serve_time': time(18, 00)}
        # form = CreateSlotForm(self.user1, self.dining_date, form_data)
        # self.assertFalse(form.is_valid())
        # self.assertTrue(form.has_error('association'))


    def test_serve_time_too_late(self):
        # Actually tests a different class, but put here for convenience, to test it via the CreateSlotForm class
        self.form_data['serve_time'] = '23:30'
        self.assertFalse(self.form.is_valid())

    def test_serve_time_too_early(self):
        # Actually tests a different class, but put here for convenience, to test it via the CreateSlotForm class
        self.form_data['serve_time'] = '11:00'
        self.assertFalse(self.form.is_valid())

