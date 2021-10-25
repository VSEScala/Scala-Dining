from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView

from directdebit.forms import UpgradeBalanceForm
from directdebit.models import DirectDebitTransaction


class UpgradeBalanceView(LoginRequiredMixin, FormView):
    """This view allows a user to upgrade their balance using direct debit."""
    template_name = 'directdebit/upgrade_balance.html'

    form_class = UpgradeBalanceForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'instance': DirectDebitTransaction(target=self.request.user.account,
                                               created_by=self.request.user)
        })
        return kwargs

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)

    success_url = reverse_lazy('credits:transaction_list')
