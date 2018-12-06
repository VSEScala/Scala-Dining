from datetime import time, date

from django.test import TestCase

from Dining.forms import CreateSlotForm
from UserDetails.models import Association, User, UserMemberships


class CreateSlotFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        """
        Do not modify the objects created here in tests, see:
        https://docs.djangoproject.com/en/2.1/topics/testing/tools/#django.test.TestCase.setUpTestData
        """
        cls.association1 = Association.objects.create(name="Auletes")
        cls.association2 = Association.objects.create(name="Ensuite")
        cls.user1 = User.objects.create_user('jan')
        # cls.user2 = User.objects.create_user('klaas')
        cls.user1_membership = UserMemberships.objects.create(related_user=cls.user1, association=cls.association1,
                                                              is_verified=True)
        cls.dining_date = date(2018, 12, 26)

    def test_creation(self):
        # Create
        form_data = {'dish': 'Kwark', 'association': self.association1, 'max_diners': 18, 'serve_time': time(17, 00)}
        form = CreateSlotForm(self.user1, form_data, date=self.dining_date)
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

        Association 2 with user 1.
        """
        # Todo: this test fails! Should add a check for the provided association
        form_data = {'dish': 'Boter', 'association': self.association2.pk, 'max_diners': 20, 'serve_time': time(18, 00)}
        # self.assertRaises()
        form = CreateSlotForm(self.user1, form_data, date=self.dining_date)
        instance = form.save()

