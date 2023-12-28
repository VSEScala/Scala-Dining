from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import FormView, View
from django.views.generic.list import ListView

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
    """Returns a CSV with transactions."""

    def has_permission(self, account) -> bool:
        """Whether the current user has permission to download the CSV.

        * Normal users can only export their own account.
        * Association board members can export the association transactions.
        * Site-wide admins can export any account.

        Args:
            account: The account to export.
        """
        if self.request.user.has_site_stats_access():
            return True
        if account.user and account.user == self.request.user:
            return True
        if account.association and self.request.user.is_board_of(account.association):
            return True
        return False

    def get(self, request, *args, pk=None, **kwargs):
        account = get_object_or_404(Account, pk=pk)

        if not self.has_permission(account):
            raise PermissionDenied

        # Stream CSV
        qs = Transaction.objects.filter_account(account).order_by("-moment")
        return StreamingHttpResponse(
            qs.csv(),
            content_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="transactions.csv"'},
        )


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
