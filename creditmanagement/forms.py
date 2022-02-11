from typing import Tuple, Any

from dal_select2.widgets import ModelSelect2
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from creditmanagement.models import Account, Transaction
from general.mail_control import send_templated_mail
from userdetails.models import User, Association

# Form fields which are used in transaction forms
USER_FORM_FIELD = forms.ModelChoiceField(User.objects.all(),
                                         required=False,
                                         widget=ModelSelect2(url='people_autocomplete',
                                                             attrs={'data-minimum-input-length': '1'}),
                                         label="User")
ASSOCIATION_FORM_FIELD = forms.ModelChoiceField(Association.objects.all(),
                                                required=False,
                                                label="Association")
SPECIAL_FORM_FIELD = forms.ModelChoiceField(Account.objects.filter(special__isnull=False),
                                            required=False,
                                            label="Bookkeeping account")


def one_of(*args) -> Tuple[Any, int]:
    """Returns the element and index of the one argument that evaluates to True.

    If multiple or none of the arguments evaluate to True, (None, -1) is returned.
    """
    el = None
    idx = -1
    for i in range(len(args)):
        if args[i]:
            if el:
                return None, -1  # Another True element was already found so multiple evaluate to True
            el = args[i]
            idx = i
    return el, idx


class TransactionForm(forms.ModelForm):
    """Allows creating transactions from a set source to a user or association target.

    Blocks a transaction if a user's account balance becomes negative.
    """

    origin = forms.CharField(disabled=True)
    target_user = USER_FORM_FIELD
    target_association = ASSOCIATION_FORM_FIELD

    class Meta:
        model = Transaction
        fields = ['origin', 'amount', 'target_user', 'target_association', 'description']
        help_texts = {
            'description': "E.g. deposit or withdrawal via board member.",
        }

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
        self.fields['target_association'].help_text = ("Provide a user or an association who will receive the money. "
                                                       "You can't provide both a user and an association.")

    def clean(self):
        cleaned_data = super().clean()
        # Check that there's exactly 1 one user or association set
        target_el, idx = one_of(cleaned_data.get('target_user'), cleaned_data.get('target_association'))
        if not target_el:
            raise ValidationError("Provide exactly one of user or association.")

        # Set target of the transaction
        self.instance.target = target_el.account

        # Check target != source
        if self.instance.target == self.instance.source:
            raise ValidationError("Receiver cannot be the same as the origin.")

        # Check balance!!
        # We block transactions made by this form that make a user account balance negative
        # (There's a race condition here when balance changes after this check, but it is not an issue in practice.)
        source = self.instance.source  # type: Account
        if source.user and source.balance < cleaned_data.get('amount'):
            raise ValidationError("Your balance is insufficient.")

        return cleaned_data


class SiteWideTransactionForm(forms.ModelForm):
    """Allows creating transactions with arbitrary source and destination.

    Should only be used by bosses. An e-mail is sent to a user when money is
    withdrawn from their account.
    """

    source_user = USER_FORM_FIELD
    source_association = ASSOCIATION_FORM_FIELD
    source_special = SPECIAL_FORM_FIELD
    target_user = USER_FORM_FIELD
    target_association = ASSOCIATION_FORM_FIELD
    target_special = SPECIAL_FORM_FIELD

    class Meta:
        model = Transaction
        fields = ['source_user', 'source_association', 'source_special',
                  'target_user', 'target_association', 'target_special', 'amount', 'description']

    def __init__(self, user: User, *args, **kwargs):
        """Constructor.

        Args:
            user: The user who is creating the transaction.
        """
        super().__init__(*args, **kwargs)
        self.instance.created_by = user

    def clean(self):
        """Converts the source and target fields into actual accounts."""
        cleaned_data = super().clean()
        # Get source
        source_el, source_idx = one_of(cleaned_data.get('source_user'),
                                       cleaned_data.get('source_association'),
                                       cleaned_data.get('source_special'))
        if not source_el:
            raise ValidationError("Provide exactly 1 transaction source.")
        # Target
        target_el, target_idx = one_of(cleaned_data.get('target_user'),
                                       cleaned_data.get('target_association'),
                                       cleaned_data.get('target_special'))
        if not target_el:
            raise ValidationError("Provide exactly 1 transaction target.")
        # Convert to actual accounts (in the case of a user or association object)
        self.instance.source = source_el if source_idx == 2 else source_el.account
        self.instance.target = target_el if target_idx == 2 else target_el.account

        # Check target != source
        if self.instance.target == self.instance.source:
            raise ValidationError("Receiver cannot be the same as the origin.")

        return cleaned_data

    def save(self, commit=True, request=None):
        """This method sends an email to the source user on save.

        Provide the request for email template rendering.
        """
        instance = super().save(commit=False)
        if commit:
            with transaction.atomic():
                # We do this in a DB transaction so that when the e-mail failed,
                # the transaction is not saved. (Not sure whether it's a good idea, but doesn't really matter)
                instance.save()
                # Send mail if the source is a user
                source = self.instance.source
                if source.user:
                    send_templated_mail('mail/transaction_created', source.user, {'transaction': instance}, request)

        return instance
