from django import forms
from .models import *

class TransactionForm(forms.ModelForm):
    origin = forms.CharField(disabled=True)
    target_user = forms.ModelChoiceField(queryset=User.objects.all().order_by('first_name'))

    def __init__(self, *args, user=None, association=None, **kwargs):
        super(TransactionForm, self).__init__(*args, **kwargs)

        # Set the transaction source
        if user:
            self.instance.source_user = user
            self.fields['origin'].initial = user
        elif association:
            self.instance.source_association = association
            self.fields['origin'].initial = association
        else:
            raise ValueError("source is neither user nor association")

    class Meta:
        model = PendingTransaction
        fields = ['origin', 'amount', 'target_user', 'target_association']

    def save(self):
        self.instance.save()

    def clean(self):
        cleaned_data = super().clean()

        # Do not allow associations to make evaporating money transactons
        # (not restircted on database level, but it doesn't make sense to order it)
        if not cleaned_data.get('target_user') and not cleaned_data.get('target_association'):
            raise ValidationError("Select a target to transfer the money to.")

        return cleaned_data
