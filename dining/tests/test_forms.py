from datetime import time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from django.http import HttpRequest

from creditmanagement.models import Transaction
from dining.forms import CreateSlotForm, SendReminderForm
from dining.models import DiningList, DiningEntryUser
from userdetails.models import Association, User, UserMembership
from utils.testing import TestPatchMixin, patch, FormValidityMixin


class CreateSlotFormTestCase(TestCase):
    def setUp(self):
        self.association1 = Association.objects.create(name="Quadrivium")
        self.user1 = User.objects.create_user('jan')
        UserMembership.objects.create(related_user=self.user1, association=self.association1, is_verified=True,
                                      verified_on=timezone.now())
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

    def test_insufficient_balance_exception(self):
        Transaction.objects.create(source=self.user1.account,
                                   target=self.association1.account,
                                   amount=Decimal('99'),
                                   created_by=self.user1)
        # Make user member of another association that has the exception
        association = Association.objects.create(name='Q', has_min_exception=True)
        UserMembership.objects.create(related_user=self.user1, association=association, is_verified=True,
                                      verified_on=timezone.now())
        self.assertTrue(self.form.is_valid())

    def test_serve_time_too_late(self):
        # Actually tests a different class, but put here for convenience, to test it via the CreateSlotForm class
        self.form_data['serve_time'] = '23:30'
        self.assertFalse(self.form.is_valid())

    def test_serve_time_too_early(self):
        # Actually tests a different class, but put here for convenience, to test it via the CreateSlotForm class
        self.form_data['serve_time'] = '11:00'
        self.assertFalse(self.form.is_valid())


class TestSendReminderForm(FormValidityMixin, TestPatchMixin, TestCase):
    fixtures = ['base', 'dining_lists']
    form_class = SendReminderForm

    def get_form_kwargs(self, **kwargs):
        kwargs.setdefault('dining_list', self.dining_list)
        return super(TestSendReminderForm, self).get_form_kwargs(**kwargs)

    def setUp(self):
        self.dining_list = DiningList.objects.get(id=1)

    def test_is_valid(self):
        """ Tests that the form is normally valid"""
        self.assertFormValid({})

    def test_invalid_all_paid(self):
        # Make all users paid
        self.dining_list.dining_entries.update(has_paid=True)
        self.assertFormHasError({}, code='all_paid')

    def test_invalid_missing_payment_link(self):
        self.dining_list.payment_link = ""
        self.dining_list.save()
        self.assertFormHasError({}, code='payment_url_missing')

    @patch('dining.forms.send_templated_mail')
    def test_mail_sending_users(self, mock_mail):

        form = self.assertFormValid({})
        request = HttpRequest()
        request.user = User.objects.get(id=1)
        form.send_reminder(request=request)

        calls = self.assert_has_call(mock_mail, arg_1="mail/dining_payment_reminder")
        # Assert that the correct number of recipients are documented
        self.assertEqual(
            len(calls[0]['args'][1]),
            DiningEntryUser.objects.filter(
                dining_list=self.dining_list,
                has_paid=False,
            ).count()
        )

        self.assertEqual(calls[0]['context']['dining_list'], self.dining_list)
        self.assertEqual(calls[0]['context']['reminder'], User.objects.get(id=1))

    @patch('dining.forms.send_templated_mail')
    def test_mail_sending_external(self, mock_mail):
        """ Tests handling of messaging for external guests added by a certain user"""

        form = self.assertFormValid({})
        request = HttpRequest()
        request.user = User.objects.get(id=1)
        form.send_reminder(request=request)

        calls = self.assert_has_call(mock_mail, arg_1="mail/dining_payment_reminder_external")
        self.assertEqual(len(calls), 2)  # ids 2 and 3 added unpaid guests

        self.assertEqual(calls[0]['context']['dining_list'], self.dining_list)
        self.assertEqual(calls[0]['context']['reminder'], User.objects.get(id=1))
        self.assertEqual(calls[0]['args'][1], User.objects.get(id=2))
        self.assertEqual(len(calls[0]['context']['guests']), 2)
        self.assertEqual(calls[1]['args'][1], User.objects.get(id=3))
        self.assertEqual(len(calls[1]['context']['guests']), 1)