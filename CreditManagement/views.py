from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from UserDetails.models import UserInformation
from .forms import create_transaction_form


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
                print(403)
                return

        # Set up the transaction
        # Get the input elements, either yourself or any association you are member of
        # Get the target (user or association)

        if request.GET:
            if request.GET['source']:
                pass

        user = UserInformation.objects.get(username=request.user.username)

        self.context['slot_form'] = create_transaction_form(user)



        return render(request, self.template, self.context)