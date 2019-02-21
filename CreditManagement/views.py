from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic.list import ListView
from CreditManagement.models import *
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from .forms import *
from django.views.generic import View
from django.http import HttpResponseForbidden, HttpResponseRedirect


class TransactionListView(ListView):
    template_name = "credit_management/history_credits.html"
    paginate_by = 10
    context_object_name = 'transactions'

    def get_queryset(self):
        return AbstractTransaction.get_all_transactions(user=self.request.user).order_by('-pk')


class TransactionAddView(LoginRequiredMixin, View):
    template_name = "credit_management/transaction_add.html"
    context = {}

    def get(self, request, association_name=None, *args, **kwargs):
        if association_name:
            association = Association.objects.get(slug=association_name)
            # If an association is given as the source, check user credentials
            if not self.check_association_permission(request.user, association):
                return HttpResponseForbidden()
            # Create the form
            self.context['slot_form'] = TransactionForm(association=association)
        else:
            self.context['slot_form'] = TransactionForm(user=request.user)
        return render(request, self.template_name, self.context)

    def post(self, request, association_name=None, *args, **kwargs):
        # Do form shenanigans
        if association_name:
            association = Association.objects.get(slug=association_name)
            # If an association is given as the source, check user credentials
            if not self.check_association_permission(request.user, association):
                return HttpResponseForbidden()
            # Create the form
            form = TransactionForm(request.POST, association=association)
        else:
            form = TransactionForm(request.POST, user=request.user)

        if form.is_valid():
            form.save()
            return HttpResponseRedirect(request.path_info)

        self.context['slot_form'] = form
        return render(request, self.template_name, self.context)

    def check_association_permission(self, user, association):
        if user.groups.filter(id=association.id).count() > 0:
            return True
        else:
            return False


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