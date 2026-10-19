from decimal import Decimal

from django.test import TestCase

from creditmanagement.models import Account, Transaction
from userdetails.models import User


class CreditTestCase(TestCase):
    """Test case for the credit models."""

    @classmethod
    def setUpTestData(cls):
        cls.a1 = Account.objects.create()
        cls.a2 = Account.objects.create()
        cls.u = User.objects.create(username="user")

    def test_balance_no_tx(self):
        """Tests balance when there are no transactions."""
        self.assertEqual(self.a1.get_balance(), Decimal("0.00"))

    def test_balance(self):
        """Tests balance when there are at least 1 source and target transaction."""
        Transaction.objects.create(
            source=self.a1, target=self.a2, amount=Decimal("8.30"), created_by=self.u
        )
        Transaction.objects.create(
            source=self.a2, target=self.a1, amount=Decimal("9.88"), created_by=self.u
        )
        self.assertEqual(self.a1.get_balance(), Decimal("1.58"))
        self.assertEqual(self.a2.get_balance(), Decimal("-1.58"))

    def test_reversal(self):
        """Tests the reversal transaction."""
        tx = Transaction.objects.create(
            source=self.a1, target=self.a2, amount=Decimal("2.64"), created_by=self.u
        )
        tx.reversal(self.u).save()
        self.assertEqual(self.a1.get_balance(), Decimal("0.00"))
        self.assertEqual(self.a2.get_balance(), Decimal("0.00"))

    def test_has_sufficient_balance_non_user_account(self):
        """Non-user accounts (associations, special) are always considered to have sufficient balance."""
        self.assertTrue(self.a1.has_sufficient_balance(Decimal("100.00")))

    def test_has_sufficient_balance_user_account(self):
        """User accounts check whether balance >= required_balance."""
        user_account = self.u.account
        self.assertTrue(user_account.has_sufficient_balance(Decimal("0.00")))
        self.assertFalse(user_account.has_sufficient_balance(Decimal("0.01")))

    def test_get_with_lock(self):
        """Account.get_with_lock fetches the instance."""
        locked = Account.get_with_lock(self.a1.pk)
        self.assertEqual(locked.pk, self.a1.pk)
