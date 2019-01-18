from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from UserDetails.models import User
from .forms import create_transaction_form


from .models import Transaction


class TransactionListView(ListView):
    template_name = "credit_management/transaction_list.html"
    paginate_by = 10
    context_object_name = 'transactions'

    def get_queryset(self):
        return Transaction.objects.with_user(self.request.user).order_by('-pk')


class AssociationTransactionListView():
    pass

        user = User.objects.get(username=request.user.username)

        self.context['slot_form'] = create_transaction_form(user)



        return render(request, self.template, self.context)


class TransactionTestView(View):

    def get(self, request, user=None):
        #content = AbstractTransaction.get_all_credits(user=user)
        #result = "These are all objects: <BR>"

        result = AbstractTransaction.get_user_credit(user=user)

        return render(request, "test.html", {'text': result})


        if content is not None:
            for i in content:
                result += "{5}: {0} or {1} to {3} or {4} for {2}  ".format(i.source_user, i.source_association, i.amount, i.target_user, i.target_association, i.description)
                #result += "{0}".format(i.amount)
                result+= "<BR>"

        return render(request, "test.html", {'text': result})
