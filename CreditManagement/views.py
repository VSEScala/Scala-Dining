from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from UserDetails.models import User
from .models import *
from .forms import create_transaction_form
from django.http import HttpResponse


from .models import Transaction

# Create your views here.

class TransactionView(View):
    context = {}
    template = "credit_management/transaction.html"

    @method_decorator(login_required)
    def get(self, request, transaction_id=None, **kwargs):
        # Get the transaction
        try:
            transaction = Transaction.objects.get(id=transaction_id)
        except Transaction.DoesNotExist:
            if transaction_id is not None:
                # TODO: throw 404 error, item not found
                return
            transaction = None

        if transaction is not None:
            # Check if user is authorised to view/alter the transaction
            if not (transaction.source_user is request.user or \
               transaction.source_association in request.user.groups):
                # 403
                return

        # Set up the transaction
        # Get the input elements, either yourself or any association you are member of
        # Get the target (user or association)

        if request.GET:
            if request.GET['source']:
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
