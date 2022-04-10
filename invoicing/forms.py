from django import forms

from creditmanagement.models import Account
from invoicing.models import InvoicedTransaction


class UpgradeBalanceForm(forms.ModelForm):
    class Meta:
        AMOUNT_CHOICES = (
            ('0.50', '€0.50'),
            ('2.00', '€2.00'),
            ('5.00', '€5.00'),
        )

        model = InvoicedTransaction
        fields = ('source', 'amount')
        labels = {
            'source': 'Association',
        }
        widgets = {
            'source': forms.RadioSelect,
            'amount': forms.RadioSelect(choices=AMOUNT_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Determine eligible associations using the target user
        #
        # 1. User must be verified member
        # 2. Association must allow invoicing
        user = self.instance.target.user
        qs = Account.objects.filter(
            association__usermembership__in=user.get_verified_memberships(),
            association__allow_invoicing=True,
        )
        self.fields['source'].queryset = qs
        self.initial['source'] = qs.first()

    def save(self, commit=True):
        tx = super().save(commit=False)  # type: InvoicedTransaction
        tx.description = "Deposit using {}".format(tx.source.association.invoicing_method)
        if commit:
            tx.save()
        return tx
