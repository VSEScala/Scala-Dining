from django.views.generic.list import ListView

from .models import Transaction


class TransactionListView(ListView):
    template_name = "credit_management/transaction_list.html"
    paginate_by = 10
    context_object_name = 'transactions'

    def get_queryset(self):
        return Transaction.objects.with_user(self.request.user).order_by('-pk')


class AssociationTransactionListView():
    pass
