from django.conf import settings
from django.db import models

from CreditManagement.models.accounts import Account


class Transaction(models.Model):
    """A transaction is a collection of accounting entries.

    This implements double-entry bookkeeping. Each transaction consists of two
    or more accounting entries. For instance for a kitchen cost payment, there
    would be a single transaction with two entries, one entry which deducts 50
    cents from the user account and another entry which adds 50 cents to the
    kitchen funds account.

    The sum of all entries in a transaction should always add up to zero. This
    helps in preventing errors (to find more about this, read online about
    double-entry bookkeeping).

    It is also possible to have more than two entries in a transaction. This
    can be used for transactions across multiple users, e.g. for Quadrivium's
    automatic bank transfers.
    """
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField()
    description = models.TextField()

    # Todo: constraint that amount of all entries sums to 0

    # @classmethod
    # def create(cls, source: Account, target: Account, created_by,
    #            created_at: datetime.datetime, min_balance: Decimal = None) -> Transaction:
    #     """
    #
    #     Args:
    #         source: The source account.
    #         target: The target account.
    #         created_by: User who created the transaction.
    #         created_at: When the transaction is created.
    #         min_balance: If given, validates that
    #
    #     Returns:
    #
    #     Raises:
    #         ValidationError: When min_balance is
    #     """
    #     # Lock the source and target account
    #
    # def reverse(self):
    #     pass


class Entry(models.Model):
    """A single credit/debit statement for an account, part of a transaction.

    Also known as a 'lot' or 'posting' or 'leg' in double-entry bookkeeping
    terminology. See the Transaction model for more details.
    """
    account = models.ForeignKey(Account, on_delete=models.PROTECT,
                                related_name='entries')
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT,
                                    related_name='entries')
    # Precision of 8 leads to 4 bytes storage excluding overhead
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    """Money amount."""
    type = models.CharField(max_length=2, choices=(('ki', 'Kitchen cost'),('ot', 'Other')))
    """Used to store type info."""


