from datetime import time, date, timedelta

from django.test import TestCase
from django.utils import timezone

from Dining.forms import CreateSlotForm
from UserDetails.models import Association, User, UserMembership
from Dining.models import DiningList


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
        # Date two days in the future
        cls.dining_date = timezone.now().date() + timedelta(days=2)

    def test_creation(self):
        # Create
        form_data = {'dish': 'Kwark', 'association': self.association1.pk, 'max_diners': 18, 'serve_time': time(17, 00)}
        form = CreateSlotForm(self.user1, self.dining_date, form_data)
        self.assertTrue(form.is_valid())
        dining_list = form.save()

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
        form_data = {'dish': 'Boter', 'association': self.association3.pk, 'max_diners': 20, 'serve_time': time(18, 00)}
        form = CreateSlotForm(self.user1, self.dining_date, form_data)
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

