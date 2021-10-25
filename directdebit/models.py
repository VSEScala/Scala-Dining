from django.db import models

from creditmanagement.models import Transaction



class DirectDebitReport(models.Model):
    """List of transactions over a period of time."""


    pass


class DirectDebitTransaction(Transaction):
    """A transaction which is handled using a direct debit.

    The source of the transaction is the association. The target is the member
    of the association.
    """
    # The report its in, if one
    report = models.ForeignKey(DirectDebitReport, on_delete=models.PROTECT, null=True, related_name='transactions')
