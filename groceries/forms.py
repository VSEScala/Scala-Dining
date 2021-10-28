from decimal import Decimal, ROUND_UP
from typing import List

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from creditmanagement.models import Transaction
from groceries.models import Payment
from userdetails.models import User


class PaymentCreateForm(forms.ModelForm):
    # This allows the user to select for who an automatic transaction should be created.
    #
    # The field is manually rendered, not using a widget. A
    # ModelMultipleChoiceField would be more appropriate but it needs a
    # queryset instead of a list of users.
    automatic_charge = forms.TypedMultipleChoiceField(required=False, coerce=int)

    class Meta:
        model = Payment
        fields = ('payment_link', 'phone_number', 'include_email', 'remarks')

    def chargeable(self) -> List[User]:
        """Returns a list of dining entries that can be charged."""
        # This is written in procedural style, it would be way more efficient to use a single SQL query
        payment = self.instance  # type: Payment
        # User should be an internal diner on the list
        users = [e.user for e in payment.dining_list.internal_dining_entries()]
        # User can't be the receiver
        users = [x for x in users if x != payment.receiver]
        # User should allow payments
        users = [x for x in users if x.allow_grocery_payments]
        # Balance should be sufficient
        cost_pp = self.get_cost_per_person()
        users = [x for x in users if x.account.get_balance() >= cost_pp]
        return users

    def get_cost_per_person(self) -> Decimal:
        """Calculates cost per person using the total cost set on the Payment instance."""
        payment = self.instance  # type: Payment
        nr_diners = payment.dining_list.diners.count()
        # Check division by 0
        if nr_diners == 0:
            return payment.total_cost
        cost_pp = payment.total_cost / nr_diners
        # Round up to remove missing cents
        return cost_pp.quantize(Decimal('.01'), rounding=ROUND_UP)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Field is only used for validation so doesn't need to be setup when the form isn't bound
        if self.is_bound:
            self.fields['automatic_charge'].choices = [(u.pk, '') for u in self.chargeable()]

    def clean(self):
        # Let's prevent creating a payment if there are no diners
        # (even though it shouldn't cause any issues).
        cleaned_data = super().clean()
        if self.instance.dining_list.diners.count() == 0:
            raise ValidationError("Can't create groceries payment when there are no diners.")
        return cleaned_data

    def save(self, commit=True):
        payment = super().save(commit=False)  # type: Payment
        payment.cost_pp = self.get_cost_per_person()

        if commit:
            with transaction.atomic():
                payment.save()

                # Create the payment entries from dining entries
                charge = self.cleaned_data['automatic_charge']
                for entry in payment.dining_list.entries.all():
                    if entry.is_internal() and entry.user.pk in charge:
                        # Charge user
                        tx = Transaction.objects.create(
                            source=entry.user.account,
                            target=payment.receiver.account,
                            amount=payment.cost_pp,
                            description="Groceries payment for {}".format(payment.dining_list),
                            created_by=payment.receiver,
                        )
                    else:
                        tx = None

                    # Users with a transaction and the receiver have paid=True
                    paid = bool(tx) or (entry.is_internal() and entry.user == payment.receiver)

                    payment.entries.create(
                        user=entry.user,
                        external_name=entry.external_name,
                        paid=paid,
                        transaction=tx,
                    )
        return payment
