from django import forms
from .models import *

class TransactionForm(forms.ModelForm):
    origin = forms.CharField(disabled=True)

    def __init__(self, *args, user=None, association=None, **kwargs):
        super(TransactionForm, self).__init__(*args, **kwargs)

        # Set the transaction source
        if user:
            self.instance.source_user = user
            self.fields['origin'].initial = user
        elif association:
            self.instance.source_associatin = association
            self.fields['origin'].initial = association
        else:
            raise ValueError("source is neither user nor association")

    class Meta:
        model = PendingTransaction
        fields = ['origin', 'amount', 'target_user', 'target_association']

    def save(self):
        self.instance.save()