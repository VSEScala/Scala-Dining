import csv
from datetime import datetime
from io import StringIO
from time import time
from urllib.parse import quote

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import BadRequest
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy, reverse
from django.utils import timezone
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
        context.update({
            'reports': InvoiceReport.objects.filter(association=self.association).order_by('-created_at'),
        })
        return context

    # def post(self, request, *args, **kwargs):
    #     # Posting will create a new report
    #     txs = InvoicedTransaction.objects.filter(source__association=self.association, report=None)
    #     if txs:
    #         # Only create report if there are transactions
    #         with transaction.atomic():
    #             report = InvoiceReport.objects.create()
    #             report.transactions.add(*txs)
    #     return redirect('invoicing-reports', association_name=self.association.slug)


class CreateReportView(LoginRequiredMixin, AssociationBoardMixin, TemplateView):
    """Shows a table of debtors and amounts, and allows to create a new report.

    This view only fetches transactions that are before the timestamp given in
    the GET query parameter. This makes sure that the fetched transactions will
    always be exactly the same when POSTing or refreshing, even if a new
    transaction was created in the meantime.
    """
    template_name = 'invoicing/report_create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        amounts = self.get_transactions().group_users()

        # Construct CSV as a long string
        with StringIO() as output:
            writer = csv.writer(output)
            writer.writerow(['username', 'name', 'email', 'amount_to_invoice'])
            for r in amounts:
                writer.writerow([r['username'], f"{r['first_name']} {r['last_name']}", r['email'], r['total_amount']])
            contents = output.getvalue()

        context.update({
            'amounts': amounts,
            # Data URL, pretty cool thing (https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/Data_URIs)
            'csv_uri': quote(contents),
        })
        return context

    def get_transactions(self):
        """Returns the uncleared transactions."""
        try:
            before = int(self.request.GET['before'])
        except (KeyError, ValueError):
            raise BadRequest("'before' parameter is invalid or missing")
        before = datetime.fromtimestamp(before, tz=timezone.utc)
        return InvoicedTransaction.objects.filter(source__association=self.association, report=None, moment__lt=before)

    def get(self, request, *args, **kwargs):
        if 'before' not in request.GET:
            # 'before' is not given, add it to the URL
            new_url = '{}?before={}'.format(
                reverse('invoicing-new-report', kwargs={'association_name': self.association.slug}),
                int(time()) - 2)  # Timestamp of 2 seconds ago (exact time doesn't matter as long as it's in the past)
            return redirect(new_url)

        return self.render_to_response(self.get_context_data(**kwargs))

    def post(self, request, *args, **kwargs):
        # Posting will clear the transactions
        txs = self.get_transactions()
        # Only create report if there are transactions
        if txs:
            with transaction.atomic():
                report = InvoiceReport.objects.create(created_by=request.user, association=self.association)
                report.transactions.add(*txs)
        return redirect('invoicing-reports', association_name=self.association.slug)


class ReportDownloadView(LoginRequiredMixin, UserPassesTestMixin, SingleObjectMixin, View):
    model = InvoiceReport

    def test_func(self):
        # Can only download if board member
        return self.request.user.is_board_of(self.get_object().association.pk)

    def write_csv(self, file):
        """Writes a report CSV file to the given file object."""
        writer = csv.writer(file)
        writer.writerow(['username', 'name', 'email', 'amount_to_invoice'])

        report = self.get_object()  # type: InvoiceReport
        for r in report.transactions.group_users():
            writer.writerow([r['username'],
                             f"{r['first_name']} {r['last_name']}".strip(),
                             r['email'],
                             r['total_amount']])

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoice_report.csv"'
        self.write_csv(response)
        return response
