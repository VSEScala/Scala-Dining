from datetime import datetime
from decimal import Decimal
from typing import Union, Optional

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum, Q
from django.utils import timezone
from django.utils.functional import cached_property

from userdetails.models import Association, User


class AccountQuerySet(models.QuerySet):
    def balance(self):
        """Annotates the QuerySet with a balance column."""
        raise NotImplementedError


class Account(models.Model):
    """Money account which can be used as a transaction source or target.

    About deletion: an account can be deleted *as long as* there are no
    transactions created for the account. This is implemented by user and
    association having on_delete=CASCADE and Transaction.source/target having
    on_delete=PROTECT.

    SQL note: it's a bit cleaner to have Account as a base entity and have
    foreign key columns on User and Association entities to the Account entity
    (the other way around as how it's now). That way the Account table won't be
    full of NULL values. We could change this.
    """

    # An account can only have one of user or association or special
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    association = models.OneToOneField(Association, on_delete=models.CASCADE, null=True)

    # Special accounts are used for bookkeeping
    # (The special accounts listed here are automatically created using a receiver.)

    SPECIAL_ACCOUNTS = [
        ('kitchen_cost', 'Kitchen cost'),
    ]
    SPECIAL_ACCOUNT_DESCRIPTION = {
        'kitchen_cost': "Account which receives the kitchen payments. "
                        "The balance indicates the money that is payed for kitchen usage "
                        "(minus withdraws from this account).",
    }
    special = models.CharField(max_length=30, unique=True, null=True, default=None, choices=SPECIAL_ACCOUNTS)

    @cached_property
    def balance(self) -> Decimal:
        tx = Transaction.objects.filter_valid()
        # 2 separate queries for the source and target sums
        # If there are no rows, the value will be made 0.00
        source_sum = tx.filter(source=self).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
        target_sum = tx.filter(target=self).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
        return target_sum - source_sum

    def get_entity(self) -> Union[User, Association, None]:
        """Returns the user or association for this account.

        Returns None when this is a special account.
        """
        if self.user:
            return self.user
        if self.association:
            return self.association
        return None

    def negative_since(self) -> Optional[datetime]:
        """Computes the date when the users balance has become negative.

        Returns:
            The computed date or None if the user balance is positive.
        """
        balance = self.balance
        if balance >= 0:
            # balance is already positive, return nothing
            return None

        # Loop over all transactions from new to old, while reversing the balance
        transactions = Transaction.objects.filter_account(self).order_by('-moment')
        for tx in transactions:
            if tx.source == self:
                balance += tx.amount
            else:
                balance -= tx.amount
            # If balance is positive now, return the current transaction date
            if balance >= 0:
                return tx.moment
        # This should not be reached, it would indicate that the starting balance was below 0
        raise RuntimeError

    def __str__(self):
        if self.get_entity():
            return str(self.get_entity())
        if self.special:
            return self.get_special_display()
        return super().__str__()

    def get_special_description(self) -> str:
        """Returns the description (when this is a bookkeeping account)."""
        return self.SPECIAL_ACCOUNT_DESCRIPTION[self.special]

    def get_transactions(self) -> models.QuerySet:
        """Returns all transactions with this account as source or target."""
        return Transaction.objects.filter_account(self)


class TransactionQuerySet(models.QuerySet):
    def filter_valid(self):
        """Filters transactions that have not been cancelled."""
        return self.filter(cancelled__isnull=True)

    def filter_account(self, account: Account):
        """Filters transactions that have the given account as source or target."""
        return self.filter(Q(source=account) | Q(target=account))


class Transaction(models.Model):
    # We do not enforce that source != target because those rows are not harmful,
    # balance is not affected when source == target.
    #
    # ForeignKey fields have a database index by default.
    source = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transaction_source_set')
    target = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transaction_target_set')
    # Amount can only be (strictly) positive
    amount = models.DecimalField(decimal_places=2, max_digits=8, validators=[MinValueValidator(Decimal('0.01'))])
    moment = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=150)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='transaction_set')

    # Implementation note on cancellation
    # Instead of an extra 'cancelled' column we could also write a method that
    # creates a new transaction that reverses this transaction. In that case
    # however it is not possible to check whether a transaction is already
    # cancelled.

    # Note 2
    # This is by no means an ideal solution and there are probably much better
    # solutions but we can easily change this. Other options:
    # - Separate table: not ideal because DRY
    # - Delete transaction: while we can't and shouldn't disallow deletion on
    #   code and database level, we should not make deletion part of the API.

    # Note 3
    # This cancelled column is risky, one might forget to filter out cancelled
    # transactions when calculating balance. We might need to filter those out
    # by default.
    cancelled = models.DateTimeField(null=True)
    cancelled_by = models.ForeignKey(User,
                                     on_delete=models.PROTECT,
                                     null=True,
                                     related_name='transaction_cancelled_set')

    objects = TransactionQuerySet.as_manager()

    def cancel(self, user: User):
        """Sets the transaction as cancelled.

        Don't forget to save afterwards.
        """
        if self.cancelled:
            raise ValueError("Already cancelled")
        self.cancelled = timezone.now()
        self.cancelled_by = user

    def is_cancelled(self) -> bool:
        return bool(self.cancelled)

    is_cancelled.boolean = True
