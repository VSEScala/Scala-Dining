from dal_select2.widgets import ModelSelect2
from django import forms
from django.utils.translation import gettext as _

from .models import *


class InitialFromGETMixin:
    def __init__(self, *args, initial_from_get=None, **kwargs):
        super(InitialFromGETMixin, self).__init__(*args, **kwargs)
        # If initial_from_get is set, adjust the stored initial values
        self.initial_from_get = initial_from_get or {}

    def get_initial_for_field(self, field, field_name):
        """
        Special implementation of initial gathering if initial values are given through request GET object
        """
        value = self.initial_from_get.get(field_name)
        if value is not None:
            return value[0] if len(value) == 1 else value

        return super(InitialFromGETMixin, self).get_initial_for_field(field, field_name)


class TransactionForm(InitialFromGETMixin, forms.ModelForm):
    origin = forms.CharField(disabled=True)

    def __init__(self, *args, user=None, association=None, **kwargs):
        super().__init__(*args, **kwargs)

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
        widgets = {
            'target_user': ModelSelect2(url='people_autocomplete', attrs={'data-minimum-input-length': '1'}),
        }


class AssociationTransactionForm(TransactionForm):

    def __init__(self, association, *args, **kwargs):
        super().__init__(*args, association=association, **kwargs)
        self.fields['target_user'].required = True

    class Meta(TransactionForm.Meta):
        fields = ['origin', 'amount', 'target_user', 'description']
        labels = {
            'target_user': 'User',
        }

    def clean(self):
        cleaned_data = super().clean()

        # Do not allow associations to make evaporating money transactons
        # (not restircted on database level, but it doesn't make sense to order it)
        if not cleaned_data.get('target_user') and not cleaned_data.get('target_association'):
            raise ValidationError("Select a target to transfer the money to.")

        return cleaned_data


class UserTransactionForm(TransactionForm):

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        self.fields['target_user'].required = False
        self.fields['target_association'].required = False

    class Meta(TransactionForm.Meta):
        fields = ['origin', 'amount', 'target_user', 'target_association', 'description']

    def clean(self):
        cleaned_data = super().clean()

        # Do not allow users to make evaporating money transactons
        # (not restircted on database level, but it doesn't make sense to order it)
        if not cleaned_data.get('target_user') and not cleaned_data.get('target_association'):
            raise ValidationError("Select a target to transfer the money to.")

        return cleaned_data


class UserDonationForm(TransactionForm):
    """
    A transactionform that allows donations to the kitchen cost
    Ideal if someone uses the kitchen without making a dining list.
    """
    target = forms.CharField(disabled=True, initial="Scala kitchen use")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, user=user, **kwargs)

    class Meta(TransactionForm.Meta):
        fields = ['origin', 'amount', 'description', 'target']


class TransactionDeleteForm(forms.Form):
    def __init__(self, transaction_obj, deleter, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transaction = transaction_obj
        self.deleter = deleter

    def clean(self):
        cleaned_data = super().clean()

        if self.transaction.confirm_moment <= timezone.now():
            raise ValidationError(_('This transaction can no longer be altered'), code='locked')

        # Validate dining list is still open (except for claimant)
        if self.transaction.source_user is not None:
            if not self.transaction.source_user == self.deleter:
                raise ValidationError(_('You are not the source for this transaction'), code='locked')
        elif self.transaction.source_association is not None:
            if not self.request.user.is_board_of(self.transaction.source_association.id):
                raise ValidationError(_('You are not the source for this transaction'), code='locked')
        else:
            RuntimeError("No source is defined, this is not possible")

        return cleaned_data

    def execute(self):
        self.transaction.delete()
