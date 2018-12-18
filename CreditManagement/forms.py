from django import forms

from CreditManagement.models import Transaction


class NewTransactionForm(forms.ModelForm):
    """
    Form for creating new transactions. (Transactions can't be modified or deleted.)
    """

    class Meta:
        model = Transaction
        fields = ['source_user', 'source_association', 'target_user', 'target_association', 'amount', 'notes']
