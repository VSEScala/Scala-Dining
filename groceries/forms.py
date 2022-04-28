from decimal import Decimal, ROUND_UP

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from groceries.models import Payment


class PaymentCreateForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ('total_cost', 'payment_link', 'remarks', 'allow_transaction')

    def get_cost_per_person(self) -> Decimal:
        """Calculates cost per person using the total cost set on the Payment instance."""
        payment = self.instance  # type: Payment
        nr_diners = payment.dining_list.diners.count()
        cost_pp = payment.total_cost / nr_diners  # If nr_diners==0, this will raise exception
        # Round up to remove missing cents
        return cost_pp.quantize(Decimal('.01'), rounding=ROUND_UP)

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
                for entry in payment.dining_list.entries.all():
                    if entry.is_internal() and entry.user == payment.receiver:
                        # We do not create an entry for the receiver
                        continue
                    payment.entries.create(
                        user=entry.user,
                        external_name=entry.external_name,
                        paid=False
                    )
        return payment
