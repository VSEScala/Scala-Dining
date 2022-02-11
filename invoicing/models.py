from django.db import models
from django.db.models import OuterRef, Subquery

from creditmanagement.models import Transaction


class InvoiceReportQuerySet(models.QuerySet):
    def annotate_tx_info(self):
        """Annotates transaction info: association, oldest and newest."""
        tx = InvoicedTransaction.objects.filter(report=OuterRef('pk'))
        return self.annotate(
            association=Subquery(tx.values('source__association')[:1]),
            oldest=Subquery(tx.order_by('moment').values('moment')[:1]),
            newest=Subquery(tx.order_by('-moment').values('moment')[:1]),
        )


class InvoiceReport(models.Model):
    """List of transactions to invoice over a period of time."""

    objects = InvoiceReportQuerySet.as_manager()

    def get_association(self):
        return self.transactions.first().source.association


class InvoicedTransaction(Transaction):
    """A transaction which is invoiced later.

    The source of the transaction is the association that will invoice the
    diner. The target is the member of the association.

    Invoiced transactions should never be cancelled, as they might be in a
    (downloaded) report.
    """
    # The report its in, if one
    report = models.ForeignKey(InvoiceReport, on_delete=models.PROTECT, null=True, related_name='transactions')
