from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from creditmanagement.forms import TransactionForm
from creditmanagement.models import Account, Transaction
from userdetails.models import User


class TransactionFormTestCase(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user("sender", email="sender@example.com")
        self.receiver = User.objects.create_user(
            "receiver", email="receiver@example.com"
        )
        # Give sender initial balance of 10.00
        special_source = Account.objects.get(special="kitchen_cost")
        Transaction.objects.create(
            source=special_source,
            target=self.sender.account,
            amount=Decimal("10.00"),
            description="Initial deposit",
            created_by=self.sender,
        )

    def test_insufficient_balance_in_clean(self):
        """Asserts that TransactionForm is invalid if user has insufficient balance."""
        data = {
            "amount": "15.00",
            "target_user": str(self.receiver.pk),
            "description": "Transfer",
        }
        form = TransactionForm(self.sender.account, self.sender, data)
        self.assertFalse(form.is_valid())
        self.assertIn("Your balance is insufficient.", form.errors.get("__all__", []))

    def test_sufficient_balance_saves_transaction(self):
        """Asserts that TransactionForm succeeds and saves transaction when balance is sufficient."""
        data = {
            "amount": "6.00",
            "target_user": str(self.receiver.pk),
            "description": "Transfer",
        }
        form = TransactionForm(self.sender.account, self.sender, data)
        self.assertTrue(form.is_valid())
        tx = form.save()
        self.assertIsNotNone(tx.pk)
        self.assertEqual(self.sender.account.get_balance(), Decimal("4.00"))
        self.assertEqual(self.receiver.account.get_balance(), Decimal("6.00"))

    def test_concurrent_overdraw_in_save_fails(self):
        """If balance drops after clean() but before save(), save() raises ValidationError."""
        data = {
            "amount": "8.00",
            "target_user": str(self.receiver.pk),
            "description": "Transfer",
        }
        form1 = TransactionForm(self.sender.account, self.sender, data)
        form2 = TransactionForm(self.sender.account, self.sender, data)
        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.save()
        self.assertEqual(self.sender.account.get_balance(), Decimal("2.00"))

        with self.assertRaises(ValidationError):
            form2.save()
        self.assertEqual(self.sender.account.get_balance(), Decimal("2.00"))
