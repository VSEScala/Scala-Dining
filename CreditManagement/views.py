from django.shortcuts import render
from django.views.generic.list import ListView
from CreditManagement.models import *
from django.views.generic import View
from .models import Transaction


class TransactionListView(ListView):
    template_name = "credit_management/transaction_list.html"
    paginate_by = 10
    context_object_name = 'transactions'

    def get_queryset(self):
        return Transaction.objects.with_user(self.request.user).order_by('-pk')


class AssociationTransactionListView:
    pass


class TransactionTestView(View):

    def get(self, request, user=None):
        result = "These are all objects: <BR>"


        content = PendingDiningListTracker.finalise_to_date(None)
        if content is not None:
            for i in content:
                result += "{0}: {1} {2}".format(i.dining_list.date, i.lockdate, i.dining_list.days_adjustable)
                #result += "{0}".format(i.amount)
                result+= "<BR>"

        return render(request, "test.html", {'text': result})


        content = AbstractTransaction.get_all_transactions(user=user)
        result = "These are all objects: <BR>"

        if content is not None:
            for i in content:
                result += "{5}: {0} or {1} to {3} or {4} for {2}  ".format(i.source_user, i.source_association, i.amount, i.target_user, i.target_association, i.description)
                #result += "{0}".format(i.amount)
                result+= "<BR>"

        return render(request, "test.html", {'text': result})
