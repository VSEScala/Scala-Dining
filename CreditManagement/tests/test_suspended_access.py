from django.test import TestCase
from django.utils import timezone

from datetime import time, timedelta

from CreditManagement.forms import UserTransactionForm
from CreditManagement.models import FixedTransaction
from UserDetails.models import Association, User, UserMembership


class CreateTransactionToUserTestcase(TestCase):
    def setUp(self):
        self.association = Association.objects.create(name='Knights')
        self.suspended_user = User.objects.create_user('Bobby boef', is_suspended=True, email="suspended@test.ing")
        self.active_user = User.objects.create_user('Eric de Engel', is_suspended=False, email="active@test.ing")

        UserMembership.objects.create(related_user=self.suspended_user, association=self.association, is_verified=True,
                                      verified_on=timezone.now())
        UserMembership.objects.create(related_user=self.active_user, association=self.association, is_verified=True,
                                      verified_on=timezone.now())
        FixedTransaction.objects.create(target_user=self.suspended_user, amount=10, order_moment=timezone.now())

    def test_cant_create_new_slot(self):
        form_data = {'target_user': self.active_user.pk, 'amount': 1}

        # Check that suspended user can not create transactions to other users
        self.form = UserTransactionForm(self.suspended_user, data=form_data)
        self.assertFalse(self.form.is_valid())

        # Check that suspended user can create transactions to associations
        form_data = {'target_association': self.association.pk, 'amount': 1}
        self.form = UserTransactionForm(self.suspended_user, data=form_data)
        self.assertTrue(self.form.is_valid())
