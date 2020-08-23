from dal_select2.widgets import ModelSelect2
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Sum

from creditmanagement.models import PendingTransaction, UserCredit, Account, Transaction
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
                                         label="User",
                                         help_text="Provide a user or an association who will receive the money. "
                                                   "You can't provide both a user and an association.")

    target_association = forms.ModelChoiceField(Association.objects.all(),
                                                required=False,
                                                label="Association")

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
    """Creates pending transactions for all members of this associations who are negative."""

    def __init__(self, *args, association=None, **kwargs):
        assert association is not None
        self.association = association
        super(ClearOpenExpensesForm, self).__init__(*args, **kwargs)

    def get_applicable_user_credits(self):
        return UserCredit.objects.filter(
            user__usermembership__association=self.association,
            balance__lt=0,  # Use this to correct for any pending transactions
        )

    @property
    def negative_members_count(self):
        return self.get_applicable_user_credits().count()

    @property
    def negative_member_credit_total(self):
        balance_sum = self.get_applicable_user_credits().aggregate(Sum('balance'))['balance__sum']
        if balance_sum is None:
            balance_sum = 0
        # Remember the - value to correct for the negative outcomes
        return "{:.2f}".format(-balance_sum)

    def clean(self):
        if not self.association.has_min_exception:
            # This does not work for associations that have no minimum balance exception
            raise ValidationError(f"{self.association} has no miniumum exception")
        if self.negative_members_count == 0:
            raise ValidationError("There are no members with a negative balance to process")

        return super(ClearOpenExpensesForm, self).clean()

    def save(self):
        credits = self.get_applicable_user_credits()
        description = f"Process open costs to {self.association}"

        for credit in credits:
            PendingTransaction.objects.create(
                source_association=self.association,
                amount=-credit.balance,
                target_user=credit.user,
                description=description
            )
