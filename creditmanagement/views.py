from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View, FormView
from django.views.generic.list import ListView

from creditmanagement.forms import TransactionForm
from creditmanagement.models import AbstractPendingTransaction, FixedTransaction, Transaction
from userdetails.models import Association


class TransactionListView(ListView):
    template_name = "credit_management/transaction_history.html"
    paginate_by = 20

    def get_queryset(self):
        return Transaction.objects.filter_account(self.request.user.account).order_by('-moment')


class TransactionAddView(LoginRequiredMixin, FormView):
    """View where a user can transfer money to someone else."""
    template_name = "credit_management/transaction_add.html"
    form_class = TransactionForm

    def get_form_kwargs(self):
        """Sets up the form instance."""
        kwargs = super().get_form_kwargs()
        kwargs['source'] = self.request.user.account
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.add_message(self.request, messages.SUCCESS, "Transaction has been successfully created.")
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('credits:transaction_list')


class AssociationTransactionAddView(TransactionAddView):
    """View where an association can transfer money to someone else."""
    template_name = 'credit_management/transaction_add_association.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        association = get_object_or_404(Association, slug=self.kwargs.get('association_name'))
        # Make sure that the user is a board member
        if not self.request.user.is_board_of(association.id):
            raise PermissionDenied
        kwargs['source'] = association.account
        return kwargs

    def get_success_url(self):
        return reverse('association_credits', kwargs={'association_name': self.kwargs.get('association_name')})


class TransactionFinalisationView(View):
    context = {}
    template_name = "credit_management/transaction_finalise.html"

    def get(self, request):
        return render(request, self.template_name, self.context)

    def post(self, request):
        self.context['transactions'] = AbstractPendingTransaction.finalise_all_expired()

        return render(request, self.template_name, self.context)


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
