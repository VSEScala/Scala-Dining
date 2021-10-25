from decimal import Decimal

from django import forms

from creditmanagement.models import Account
from invoicing.models import InvoicedTransaction


class UpgradeBalanceForm(forms.ModelForm):
    # Todo: change the amount and source fields to a radio buttons widget, because that's more appropriate here.
    AMOUNT_CHOICES = (
        ('0.50', '€0.50'),
        ('2.00', '€2.00'),
        ('5.00', '€5.00'),
        ('10.00', '€10.00'),
    )

    amount = forms.TypedChoiceField(coerce=Decimal, choices=AMOUNT_CHOICES)

    class Meta:
        model = InvoicedTransaction
        fields = ('source',)
        labels = {
            'source': 'Association',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Determine eligible associations using the target user
        user = self.instance.target.user
        self.fields['source'].queryset = Account.objects.filter(
            association__usermembership__in=user.get_verified_memberships())

    def save(self, commit=True):
        tx = super().save(commit=False)  # type: InvoicedTransaction
        tx.amount = self.cleaned_data['amount']
        tx.description = "Invoiced using {}".format(tx.source.association.invoicing_method)
        if commit:
            tx.save()
        return tx
