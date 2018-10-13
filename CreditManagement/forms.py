from django import forms
from .models import Transaction
from UserDetails.models import Association, UserInformation

def create_transaction_form(user, transaction=None, source=None):
    """
    Return the slot form class specefied for the specific user
    :param user: The current user
    :return: The form
    """

    # Add the user itself and all its aphiliated associations to the source list
    source_choices = []
    source_choices.append(("self", user))
    for association in Association.objects.filter(user__id=user.id):
        source_choices.append((association.associationdetails.shorthand, association))

    # If the current transaction already exists, check if the source is in the list, if not, add it.
    source_position = -1
    if transaction is not None:
        for i in range(len(source_choices)):
            if source_choices[i][1] == transaction.source():
                source_position = i

        if source_position == -1:
            source_position = len(source_position)
            source_choices.append(source)

    class TransactionForm(forms.ModelForm):
        source_field = forms.ChoiceField(choices=source_choices)

        class Meta:
            model = Transaction
            fields = ('source_field','amount','description')

        def __init__(self, source_position = -1, *args, **kwargs):
            super(TransactionForm, self).__init__(*args, **kwargs)

            # If only one source option is availlable, set that option and disable the choice list
            if len(source_choices) == 1:
                self.fields['source_field'].disabled = True
                self.fields['source_field'].initial = 0
            else:
                # Set the initial position if it differs
                if source_position > -1:
                    self.fields['source_field'].initial = source_position

        def save(self):
            pass

    return TransactionForm(source_position=source_position)
