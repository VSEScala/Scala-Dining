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


class TransactionTestView(View):

    def get(self, request, user=None):

        result = self.annotate_users()

        #result = self.annotate_users()
        return render(request, "test.html", {'text': result})

    def do_stuff(self, id=0):
        content = User.objects.get(id=7)
        content = content.usercredit
        result = str(content.balance)

        return result

    def annotate_users(self):
        content = AbstractTransaction.get_all_transactions()
        #content = AbstractTransaction.get_all_transactions(association=Association.objects.all())
        result = "These are all objects: <BR>"

        if content is not None:
            for i in content:
                #result += "{0}: {1}".format(i, i.balance_pending_normal)
                #result += "{0}: {1} = {2} + {3} ({4})".format(i, i.balance, i.balance_fixed, i.balance_pending, i.balance_pending_dining)
                result += "{5}: {0} or {1} to {3} or {4} for {2}  ".format(i.source_user, i.source_association, i.amount, i.target_user, i.target_association, i.description)
                #result += "{0}".format(i.amount)
                result+= "<BR>"
        return result
