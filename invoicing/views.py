import csv

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, TemplateView
from django.views.generic.detail import SingleObjectMixin

from invoicing.forms import UpgradeBalanceForm
from invoicing.models import InvoicedTransaction, InvoiceReport
from userdetails.models import Association
from userdetails.views_association import AssociationBoardMixin


class UpgradeBalanceView(LoginRequiredMixin, FormView):
    """This view allows a user to upgrade their balance using direct debit."""
    template_name = 'invoicing/upgrade_balance.html'

    form_class = UpgradeBalanceForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'instance': InvoicedTransaction(target=self.request.user.account,
                                            created_by=self.request.user)
        })
        return kwargs

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'eligible_associations': Association.objects.filter(allow_invoicing=True).order_by('name')
        })
        return context

    success_url = reverse_lazy('credits:transaction_list')


class ReportsView(LoginRequiredMixin, AssociationBoardMixin, TemplateView):
    template_name = 'invoicing/reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # This subquery is to annotate reports with their first transaction time, for ordering
        context.update({
            'unreported': InvoicedTransaction.objects.filter(source__association=self.association,
                                                             report=None),
            'reports': InvoiceReport.objects.annotate_tx_info().filter(
                association=self.association).order_by('-oldest'),
        })
        return context

    def post(self, request, *args, **kwargs):
        # Posting will create a new report
        txs = InvoicedTransaction.objects.filter(source__association=self.association, report=None)
        if txs:
            # Only create report if there are transactions
            with transaction.atomic():
                report = InvoiceReport.objects.create()
                report.transactions.add(*txs)
        return redirect('invoicing-reports', association_name=self.association.slug)


def report_csv(file, report: InvoiceReport):
    """Writes a report CSV file to the given file object."""
    writer = csv.writer(file)
    writer.writerow(['name', 'email', 'amount_to_invoice'])

    # Group by target (user) and sum amounts
    #
    # For summing, it's not checked if there are cancelled transactions, but there shouldn't be anyway
    rows = report.transactions.values('target',
                                      'target__user__first_name',
                                      'target__user__last_name',
                                      'target__user__email').annotate(total_amount=Sum('amount'))
    for r in rows:
        name = "{} {}".format(r['target__user__first_name'], r['target__user__last_name'])
        writer.writerow([name, r['target__user__email'], r['total_amount']])


class ReportDownloadView(LoginRequiredMixin, UserPassesTestMixin, SingleObjectMixin, View):
    model = InvoiceReport

    def test_func(self):
        # Can only download if board member
        return self.request.user.is_board_of(self.get_object().get_association().pk)

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoice_report.csv"'
        report_csv(response, self.get_object())
        return response
