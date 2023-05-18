from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import FormView, View
from django.views.generic.list import ListView

from creditmanagement.csv import write_transactions_csv
from creditmanagement.forms import TransactionForm
from creditmanagement.models import Account, Transaction


class TransactionListView(LoginRequiredMixin, ListView):
    template_name = "credit_management/transaction_history.html"
    paginate_by = 20

    def get_queryset(self):
        return Transaction.objects.filter_account(self.request.user.account).order_by(
            "-moment"
        )


class TransactionCSVView(LoginRequiredMixin, View):
    """Returns a CSV with transactions of the current user."""

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="user_transactions.csv"'
        qs = Transaction.objects.filter_account(request.user.account).order_by(
            "-moment"
        )
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
        kwargs["source"] = self.get_source()  # Set transaction source/origin
        kwargs["user"] = self.request.user  # Set created_by
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.add_message(
            self.request, messages.SUCCESS, "Transaction has been successfully created."
        )
        return HttpResponseRedirect(self.get_success_url())

    def get_source(self) -> Account:
        """Returns the source/origin for the transaction."""
        raise NotImplementedError


class TransactionAddView(LoginRequiredMixin, TransactionFormView):
    """View where a user can transfer money to someone else."""

    template_name = "credit_management/transaction_add.html"
    success_url = reverse_lazy("credits:transaction_list")

    def get_source(self) -> Account:
        return self.request.user.account


# MoneyObtainmentView is removed in favor of Site Credits tab
