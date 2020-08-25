from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import View, FormView
from django.views.generic.list import ListView

from creditmanagement.csv import write_transactions_csv
from creditmanagement.forms import TransactionForm
from creditmanagement.models import FixedTransaction, Transaction, Account
from userdetails.models import Association


class TransactionListView(LoginRequiredMixin, ListView):
    template_name = "credit_management/transaction_history.html"
    paginate_by = 20

    def get_queryset(self):
        return Transaction.objects.filter_account(self.request.user.account).order_by('-moment')


class TransactionCSVView(LoginRequiredMixin, View):
    """Returns a CSV with transactions of the current user."""

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="user_transactions.csv"'
        # We only include non-cancelled transactions
        qs = Transaction.objects.filter_valid().filter_account(request.user.account).order_by('-moment')
        write_transactions_csv(response, qs, request.user.account)
        return response


class TransactionFormView(FormView):
    """Base class for a view with a create transaction form.

    A subclass needs to override get_source(), set the success URL and set the
    template name.
    """
    form_class = TransactionForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['source'] = self.get_source()  # Set transaction source/origin
        kwargs['user'] = self.request.user  # Set created_by
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.add_message(self.request, messages.SUCCESS, "Transaction has been successfully created.")
        return HttpResponseRedirect(self.get_success_url())

    def get_source(self) -> Account:
        """Returns the source/origin for the transaction."""
        raise NotImplementedError


class TransactionAddView(LoginRequiredMixin, TransactionFormView):
    """View where a user can transfer money to someone else."""
    template_name = "credit_management/transaction_add.html"
    success_url = reverse_lazy('credits:transaction_list')

    def get_source(self) -> Account:
        return self.request.user.account


class MoneyObtainmentView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        # Only superusers can access this page
        if not request.user.is_superuser:
            return HttpResponseForbidden
        # Todo: allow access by permission
        # Todo: linkin in interface

        date_end = request.GET.get('to', None)
        if date_end:
            date_end = datetime.strptime(date_end, '%d/%m/%y')
        else:
            date_end = timezone.now()

        date_start = request.GET.get('from', None)
        if date_start:
            date_start = datetime.strptime(date_start, '%d/%m/%y')
        else:
            date_start = date_end

        # Get all fixed transactions in the date range
        transactions = FixedTransaction.objects.filter(confirm_moment__gte=date_start, confirm_moment__lte=date_end)
        # Aggregate the values
        amount_in = transactions.filter(target_user__isnull=True,
                                        target_association__isnull=True).aggregate(sum=Sum('amount'))
        amount_out = transactions.filter(source_user__isnull=True,
                                         source_association__isnull=True).aggregate(sum=Sum('amount'))

        # Create the response
        message = "Time from {date_start} to {date_end}:\nIn: {amount_in}\nOut: {amount_out}"
        message = message.format(date_start=date_start, date_end=date_end,
                                 amount_in=amount_in['sum'], amount_out=amount_out['sum'])
        return HttpResponse(message, content_type='text/plain')
