from django.shortcuts import render
from django.views.generic.list import ListView
from CreditManagement.models import *
from django.views.generic import View


class TransactionListView(ListView):
    template_name = "credit_management/history_credits.html"
    paginate_by = 10
    context_object_name = 'transactions'

    def get_queryset(self):
        return AbstractTransaction.get_all_transactions(user=self.request.user).order_by('-pk')


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
