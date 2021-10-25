from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from creditmanagement.models import Transaction
from dining.models import DiningList
from userdetails.models import User


class Payment(models.Model):
    """A groceries payment, where 1 person receives the grocery costs from the other diners."""
    dining_list = models.ForeignKey(DiningList, on_delete=models.PROTECT)
    receiver = models.ForeignKey(User, on_delete=models.PROTECT)
    # Total groceries cost is not really necessary, but we'll store it anyway as a nice memory
    total_cost = models.DecimalField('total groceries cost',
                                     max_digits=8,
                                     decimal_places=2,
                                     validators=[MinValueValidator(Decimal('0.01'))])
    # Cost per person can be derived from total cost (not the other way around
    # because rounding took place). However let's store it anyway in case we
    # later want to change how cost_pp is derived from total cost.
    cost_pp = models.DecimalField('groceries cost per person',
                                  max_digits=8,
                                  decimal_places=2,
                                  validators=[MinValueValidator(Decimal('0.01'))])
    payment_link = models.URLField(
        blank=True,
        help_text="E.g. Tikkie or ING Payment Request."
                  " Tip: use a payment link with variable amount, then you won't need to change it the next time.")
    phone_number = models.CharField(max_length=100,
                                    blank=True,
                                    help_text="This makes it easier to contact you for payment issues.")
    include_email = models.BooleanField('include e-mail',
                                        default=True,
                                        help_text="Include your account e-mail address in the message to all diners.")
    remarks = models.CharField(max_length=200,
                               blank=True,
                               help_text="For instance an IBAN number if you can't provide a payment link.")

    created_at = models.DateTimeField(default=timezone.now)

    def paid(self):
        """Returns a QuerySet of paid entries."""
        return self.entries.filter(paid=True)


class PaymentEntry(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name='entries')
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    # Just like for dining list entries, external entries have to be reflected here as well
    external_name = models.CharField(max_length=100, blank=True)
    paid = models.BooleanField(default=False)
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, null=True)

    def is_external(self):
        return bool(self.external_name)
