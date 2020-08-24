from dal_select2.widgets import ModelSelect2
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from creditmanagement.models import Account, Transaction
from userdetails.models import User, Association


class TransactionForm(forms.ModelForm):
    origin = forms.CharField(disabled=True)

    def __init__(self, source: Account, user: User, *args, **kwargs):
        """Constructor.

        Args:
            source: The account that is used as source of the transaction.
            user: The user who is creating the transaction.
        """
        super().__init__(*args, **kwargs)
        self.instance.source = source
        self.instance.created_by = user
        self.fields['origin'].initial = str(source)

    target_user = forms.ModelChoiceField(User.objects.all(),
                                         required=False,
                                         widget=ModelSelect2(url='people_autocomplete'),
                                         label="User")

    target_association = forms.ModelChoiceField(Association.objects.all(),
                                                required=False,
                                                label="Association",
                                                help_text="Provide a user or an association who will receive the money. "
                                                          "You can't provide both a user and an association.")

    class Meta:
        model = Transaction
        fields = ['origin', 'amount', 'target_user', 'target_association', 'description']
        help_texts = {
            'description': "E.g. deposit via board member."
        }

    def clean(self):
        cleaned_data = super().clean()
        # Check that there's exactly 1 one user or association set
        # (This check is just for convenience, it is enforced on database level.)
        target_user = cleaned_data.get('target_user')
        target_association = cleaned_data.get('target_association')
        if not target_user and not target_association:
            raise ValidationError("Provide one of user or association.")
        if target_user and target_association:
            raise ValidationError("Provide only one of user or association.")

        # Set target of the transaction
        self.instance.target = target_user.account if target_user else target_association.account

        # Check target != source
        if self.instance.target == self.instance.source:
            raise ValidationError("Receiver cannot be the same as the origin.")

        # Check balance!!
        # We block transactions made by this form that make a user account balance negative
        # (Note that there's a race condition here, but it is not an issue in practice.)
        source = self.instance.source  # type: Account
        if source.user and source.get_balance() < cleaned_data.get('amount'):
            raise ValidationError("Your balance is insufficient.")

        return cleaned_data


class ClearOpenExpensesForm(forms.Form):
    """Creates transactions for all members of this association who are negative."""

    description = forms.CharField(max_length=150, help_text="Is displayed on each user's transaction overview, "
                                                            "e.g. in the case of Quadrivium it could be 'Q-rekening'.")

    def __init__(self, *args, association=None, user=None, **kwargs):
        # Calculate and create the transactions that need to be applied

        # Get all verified members. Probably nicer to create a helper method for this.
        members = User.objects.filter(usermembership__association=association, usermembership__is_verified=True)
        self.transactions = []
        for m in members:
            balance = m.account.get_balance()
            if balance < 0:
                # Construct a transaction for each member with negative balance
                tx = Transaction(source=association.account,
                                 target=m.account,
                                 amount=-balance,
                                 created_by=user)  # Description needs to be set later
                self.transactions.append(tx)
        super().__init__(*args, **kwargs)

    def save(self):
        """Saves the transactions to the database."""
        if not self.is_valid():
            raise RuntimeError
        desc = self.cleaned_data.get('description')
        with transaction.atomic():
            for tx in self.transactions:
                tx.description = desc
                tx.save()
