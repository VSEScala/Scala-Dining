from decimal import Decimal

from django.db import models
from django.db.models import Sum, F
from django.utils import timezone

from creditmanagement.models import Transaction
from userdetails.models import User, Association


class InvoiceReport(models.Model):
    """List of transactions to invoice over a period of time."""
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    # Association should be the same as the source association set on all transactions in this report
    association = models.ForeignKey(Association, on_delete=models.PROTECT)

    def total_amount(self):
        return self.transactions.aggregate(amount=Sum('amount'))['amount'] or Decimal('0.00')


class InvoicedTransactionQuerySet(models.QuerySet):
    def group_users(self):
        """Groups by users and sums the amounts.

        Returns a QuerySet of dictionaries with the columns total_amount,
        first_name, last_name and email.
        """
        # For summing, it's not checked if there are cancelled transactions, but there shouldn't be anyway
        return self.values('target').annotate(total_amount=Sum('amount'),
                                              username=F('target__user__username'),
                                              first_name=F('target__user__first_name'),
                                              last_name=F('target__user__last_name'),
                                              email=F('target__user__email'))


class InvoicedTransaction(Transaction):
    """A transaction which is invoiced (debited) later.

    The source of the transaction is the association that will invoice the
    diner. The target is the member of the association.

    Invoiced transactions should never be cancelled, as they might be in a
    (downloaded) report.
    """
    # The report its in, if one
    report = models.ForeignKey(InvoiceReport, on_delete=models.PROTECT, null=True, related_name='transactions')

    objects = InvoicedTransactionQuerySet.as_manager()
