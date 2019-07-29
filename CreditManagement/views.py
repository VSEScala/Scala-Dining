from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic.list import ListView
from django.core.exceptions import PermissionDenied
from CreditManagement.models import *
from django.contrib import messages
from django.utils.translation import gettext as _
from .forms import UserTransactionForm, AssociationTransactionForm, UserDonationForm, TransactionDeleteForm
from django.views.generic import View, TemplateView
from django.http import HttpResponseForbidden, HttpResponseRedirect, HttpResponse


class TransactionListView(ListView):
    template_name = "credit_management/history_credits.html"
    paginate_by = 10
    context_object_name = 'transactions'

    def get_queryset(self):
        return AbstractTransaction.get_all_transactions(user=self.request.user).order_by('-order_moment')


class CustomAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        permission_check = self.check_access_permission(request)
        if permission_check is not None:
            return permission_check
        return super(CustomAccessMixin, self).dispatch(request, *args, **kwargs)

    def check_access_permission(self, request):
        return None


class TransactionAlterView(LoginRequiredMixin, CustomAccessMixin, TemplateView):
    template_name = None
    template_add_name = "credit_management/transaction_add.html"
    template_edit_name = "credit_management/transaction_edit.html"

    def get_transaction(self):
        transaction_id = self.request.GET.get('id', None)
        try:
            return PendingTransaction.objects.get(pk=transaction_id)
        except PendingTransaction.DoesNotExist:
            return None

    def get_form(self, transaction=None, data=None):
        raise NotImplementedError()

    def get_context_data(self, *args, **kwargs):
        context = super(TransactionAlterView, self).get_context_data(*args, **kwargs)

        transaction_obj = self.get_transaction()
        # get the form
        context['form'] = self.get_form(transaction=transaction_obj)

        context['redirect'] = self.request.GET.get('redirect')
        context['chain'] = self.request.GET.get('chain', False)

        # Set the correct template
        if transaction_obj is None:
            self.template_name = self.template_add_name
        else:
            self.template_name = self.template_edit_name
        return context

    def post(self, request):
        transaction_obj = self.get_transaction()
        form = self.get_form(transaction=transaction_obj, data=request.POST)

        if form.is_valid():
            form.save()
            if transaction_obj is None:
                messages.add_message(request, messages.SUCCESS, _("Transaction has been added successfully."))
            else:
                messages.add_message(request, messages.SUCCESS, _("Transaction has been changed successfully."))

            if 'add_another' in request.POST:
                url = request.path_info + "?chain=True"
                if request.GET.get('redirect'):
                    url += "&redirect=" + request.GET.get('redirect')
                if request.GET.get('amount'):
                    url += "&amount=" + request.GET.get('amount')
                return HttpResponseRedirect(url)

            return HttpResponseRedirect(request.GET.get('redirect', request.path_info))

        context = self.get_context_data()
        context['form'] = form
        return render(request, self.template_name, context)


class TransactionUserView(TransactionAlterView):
    def get_form(self, transaction=None, data=None):
        return UserTransactionForm(self.request.user,
                                   initial_from_get=self.request.GET,
                                   data=data,
                                   instance=transaction)

    def check_access_permission(self, request):
        transaction_id = request.GET.get('id', None)

        if transaction_id is not None:
            # get the instance
            t_order = get_object_or_404(PendingTransaction, pk=transaction_id)
            if t_order.source_user != request.user:
                return HttpResponseForbidden("You do not have access to this transaction")
            if t_order.confirm_moment <= timezone.now():
                return HttpResponseForbidden("This transaction can no longer be altered")

        return super(TransactionUserView, self).check_access_permission(request)


class DonationView(TransactionUserView):
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


class TransactionAssociationView(TransactionAlterView):
    def check_access_permission(self, request):
        association_name = self.kwargs.get('association_name')
        association = get_object_or_404(Association, slug=association_name)

        transaction_id = request.GET.get('id', None)

        if transaction_id is not None:
            # If an association is given as the source, check user credentials
            if not self.request.user.is_board_of(association.id):
                return HttpResponseForbidden("You do not have access to this transaction")
            t_order = get_object_or_404(PendingTransaction, pk=transaction_id)
            if t_order.confirm_moment <= timezone.now():
                return HttpResponseForbidden("This transaction can no longer be altered")
        else:
            if not self.request.user.is_board_of(association.id):
                return HttpResponseForbidden("You can not make transactions for this association")

        return super(TransactionAssociationView, self).check_access_permission(request)

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

    def post(self, request, association_name=None):
        return super(TransactionAssociationView, self).post(request)


class TransactionDeleteView(CustomAccessMixin, TemplateView):
    template_name = "credit_management/transaction_delete.html"

    def get_context_data(self, **kwargs):
        context = super(TransactionDeleteView, self).get_context_data(**kwargs)
        tr_obj = self.get_transaction()

        target = tr_obj.target()
        target = target if target is not None else "Scala Kitchen"
        context['transaction_text'] = "€{amount} to {target}".format(amount=tr_obj.amount, target=target)

        return context

    def post(self, request):
        form = TransactionDeleteForm(self.get_transaction(), self.request.user, data={})

        if form.is_valid():
            form.execute()
            messages.success(request, "Transaction has successfully been deleted")
        else:
            for error in form.non_field_errors():
                messages.error(request, error)

        return HttpResponseRedirect(request.GET.get('redirect'))

    def get_transaction(self):
        transaction_id = self.request.GET.get('id', None)
        try:
            return PendingTransaction.objects.get(pk=transaction_id)
        except PendingTransaction.DoesNotExist:
            return None

    def check_access_permission(self, request):
        transaction_id = request.GET.get('id', None)

        if transaction_id is not None:
            # get the instance
            t_order = get_object_or_404(PendingTransaction, pk=transaction_id)
            if t_order.source_user != request.user:
                return HttpResponseForbidden("You do not have access to this transaction")
            if t_order.confirm_moment <= timezone.now():
                return HttpResponseForbidden("This transaction can no longer be altered")

        return super(TransactionDeleteView, self).check_access_permission(request)


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
