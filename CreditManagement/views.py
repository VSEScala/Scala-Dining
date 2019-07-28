from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic.list import ListView
from django.core.exceptions import PermissionDenied
from CreditManagement.models import *
from django.contrib import messages
from django.utils.translation import gettext as _
from .forms import UserTransactionForm, AssociationTransactionForm, UserDonationForm
from django.views.generic import View, TemplateView
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse


class TransactionListView(ListView):
    template_name = "credit_management/history_credits.html"
    paginate_by = 10
    context_object_name = 'transactions'

    def get_queryset(self):
        return AbstractTransaction.get_all_transactions(user=self.request.user).order_by('-order_moment')


class TransactionAccessMixin:
    template_name = None
    template_add_name = "credit_management/transaction_add.html"
    template_edit_name = "credit_management/transaction_edit.html"

    def dispatch(self, request, *args, **kwargs):
        """ If a specific instance is given, check the access rights."""
        id = request.GET.get('id', None)
        if id is not None:
            # get the instance
            t_order = get_object_or_404(PendingTransaction, pk=id)
            if t_order.source_user != request.user:
                raise PermissionDenied("You do not have access to this transaction")
            if t_order.confirm_moment <= timezone.now():
                raise PermissionDenied("This transaction can no longer be altered")

        return super().dispatch(request, *args, **kwargs)

    def get_transaction(self):
        transaction_id = self.request.GET.get('id', None)
        try:
            return PendingTransaction.objects.get(pk=transaction_id)
        except PendingTransaction.DoesNotExist:
            return None

    def get_form(self, transaction=None, data=None):
        raise NotImplementedError()

    def get_context_data(self, *args, **kwargs):
        context = super(TransactionAccessMixin, self).get_context_data(*args, **kwargs)

        transaction = self.get_transaction()
        # get the form
        context['form'] = self.get_form(transaction=transaction)

        # Set the correct template
        if transaction is None:
            self.template_name = self.template_add_name
        else:
            context['redirect'] = self.request.GET.get('redirect')
            self.template_name = self.template_edit_name

        return context

    def post(self, request):
        transaction = self.get_transaction()
        form = self.get_form(transaction=transaction, data=request.POST)

        if form.is_valid():
            form.save()
            if transaction is None:
                messages.add_message(request, messages.SUCCESS, _("Transaction has been added successfully."))
            else:
                messages.add_message(request, messages.SUCCESS, _("Transaction has been changed successfully."))

            return HttpResponseRedirect(request.GET.get('redirect', request.path_info))

        context = self.get_context_data()
        context['form'] = form
        return render(request, self.template_name, context)


class DonationView(LoginRequiredMixin, TransactionAccessMixin, TemplateView):
    def get_form(self, transaction=None, data=None):
        if transaction is None:
            initial = {'amount': 0.5}
        else:
            initial = {}

        return UserDonationForm(self.request.user,
                                initial_from_get=self.request.GET,
                                initial=initial,
                                data=data,
                                instance=transaction)


class TransactionUserView(LoginRequiredMixin, TransactionAccessMixin, TemplateView):
    def get_form(self, transaction=None, data=None):
        return UserTransactionForm(self.request.user,
                                   initial_from_get=self.request.GET,
                                   data=data,
                                   instance=transaction)


class TransactionAssociationView(LoginRequiredMixin, TransactionAccessMixin, TemplateView):
    def get_form(self, transaction=None, data=None):
        association_name = self.kwargs.get('association_name')
        association = Association.objects.get(slug=association_name)
        # If an association is given as the source, check user credentials
        if not self.request.user.is_board_of(association.id):
            return HttpResponseForbidden()
        # Create the form
        return AssociationTransactionForm(association,
                                          initial_from_get=self.request.GET,
                                          data=data,
                                          instance=transaction)

class AssociationTransactionListView:
    pass


class UserTransactionListView(ListView):
    pass


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
        from django.db.models import Q, Count

        # Only superusers can access this page
        if not request.user.is_superuser:
            return HttpResponseForbidden
        # Todo: allow access by permission
        # Todo: linkin in interface

        # Get the end date

        # Filter on end date
        date_end = request.GET.get('to', None)
        if date_end:
            date_end = datetime.strptime(date_end, '%d/%m/%y')
        else:
            date_end = timezone.now()

        # Filter on a start date
        date_start = request.GET.get('from', None)
        if date_start:
            date_start = datetime.strptime(date_start, '%d/%m/%y')
        else:
            date_start = date_end

        # Get all fixed transactions in the date range
        transactions = FixedTransaction.objects. \
            filter(confirm_moment__gte=date_start,
                   confirm_moment__lte=date_end)
        # Aggregate the values
        from django.db.models import Sum
        amount_in = transactions.filter(target_user__isnull=True,
                                        target_association__isnull=True).aggregate(sum=Sum('amount'))

        amount_out = transactions.filter(source_user__isnull=True,
                                         source_association__isnull=True).aggregate(sum=Sum('amount'))

        # Create the response
        message = "Time from {date_start} to {date_end}:<br>In: {amount_in}<br>Out: {amount_out}"
        message = message.format(date_start=date_start, date_end=date_end,
                                 amount_in=amount_in['sum'], amount_out=amount_out['sum'])

        # Return the respnonse
        return HttpResponse(message)
