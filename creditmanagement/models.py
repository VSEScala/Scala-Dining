from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator, Optional, Union

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Case, F, Max, Q, QuerySet, Sum, When
from django.utils.timezone import now

from creditmanagement.csv import transactions_csv
from userdetails.models import Association, User


class AccountManager(models.Manager):
    def get_by_natural_key(self, type, name=None):
        # See https://docs.djangoproject.com/en/4.1/topics/serialization/#natural-keys
        if type.lower() == "user":
            return self.get(user=User.objects.get_by_natural_key(name))
        elif type.lower() == "association":
            return self.get(association=Association.objects.get_by_natural_key(name))
        else:
            return self.get(special=type)


class Account(models.Model):
    """Money account which can be used as a transaction source or target."""

    # An account can only have one of user or association or special
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)
    association = models.OneToOneField(
        Association, on_delete=models.CASCADE, blank=True, null=True
    )

    # Special accounts are used for bookkeeping
    # (The special accounts listed here are automatically created using a receiver.)

    SPECIAL_ACCOUNTS = [
        ("kitchen_cost", "Kitchen cost"),
    ]
    SPECIAL_ACCOUNT_DESCRIPTION = {
        "kitchen_cost": "Account which receives the kitchen payments. "
        "The balance indicates the money that is payed for kitchen usage "
        "(minus withdraws from this account).",
    }
    special = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        null=True,
        default=None,
        choices=SPECIAL_ACCOUNTS,
    )

    objects = AccountManager()

    def get_balance(self) -> Decimal:
        qs = Transaction.objects.all()
        # 2 separate queries for the source and target sums
        # If there are no rows, the value will be made 0.00
        source_sum = qs.filter(source=self).aggregate(sum=Sum("amount"))[
            "sum"
        ] or Decimal("0.00")
        target_sum = qs.filter(target=self).aggregate(sum=Sum("amount"))[
            "sum"
        ] or Decimal("0.00")
        return target_sum - source_sum

    get_balance.short_description = "Balance"  # (used in admin site)

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
        balance = self.get_balance()
        if balance >= 0:
            # balance is already positive, return nothing
            return None

        # Loop over all transactions from new to old, while reversing the balance
        transactions = Transaction.objects.filter_account(self).order_by("-moment")
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

    def get_transactions(self) -> QuerySet:
        """Returns all transactions with this account as source or target."""
        return Transaction.objects.filter_account(self)


class TransactionQuerySet(QuerySet):
    def filter_account(self, account: Account):
        """Filters transactions that have the given account as source or target."""
        return self.filter(Q(source=account) | Q(target=account))

    def csv(self) -> Iterator:
        """Returns an iterator yielding a CSV file."""
        return transactions_csv(self)

    def group_by_account(self, group_users=False, key="account"):
        """Group transactions by source and target account.

        Args:
            group_users: If True, user accounts are grouped together and given
                key `None`.
            key: The name given to the account ID annotation.

        Returns:
            A Transaction QuerySet tuple with respectively the source and
            target grouped by account.
        """
        if group_users:
            # Set the group key to NULL for all user accounts
            source_query = Case(
                When(source__user__isnull=False, then=None), default="source"
            )
            target_query = Case(
                When(target__user__isnull=False, then=None), default="target"
            )
        else:
            source_query = F("source")
            target_query = F("target")

        # Annotate and group by key
        return (
            self.annotate(**{key: source_query}).values(key),
            self.annotate(**{key: target_query}).values(key),
        )

    def sum_by_account(
        self, group_users=False, latest=False
    ) -> dict[int | None, tuple[Decimal, Decimal] | tuple[Decimal, Decimal, datetime]]:
        """Sums the amounts in the QuerySet, grouped by account.

        Computes for each account that occurs in the QuerySet, the total
        balance increase and decrease sum, over all transactions in this
        QuerySet.

        Args:
            group_users: See `TransactionQuerySet.group_by_account`.
            latest: When `True`, include the last transaction date in the tuple.

        Returns:
            A dictionary with as key the account id or None when the account is
            for a user and group_users is True. The value is a tuple with the
            increase and reduce sum (possibly 0).
        """
        source_qs, target_qs = self.group_by_account(group_users=group_users)

        reduction = source_qs.annotate(reduction=Sum("amount"))
        increase = target_qs.annotate(increase=Sum("amount"))

        if latest:
            reduction = reduction.annotate(last_source_tx=Max("moment"))
            increase = increase.annotate(last_target_tx=Max("moment"))

        # Merge on account key
        merged = {e["account"]: dict(e) for e in reduction}
        for e in increase:
            merged.setdefault(e["account"], {}).update(e)

        # Convert to (increase, reduction) tuple
        result = {
            account: (
                val.get("increase", Decimal("0.00")),
                val.get("reduction", Decimal("0.00")),
            )
            for account, val in merged.items()
        }

        if latest:
            # Add latest transaction moment
            #
            # The tuple becomes (increase, reduction, last_date)
            min_date = datetime(1, 1, 1, tzinfo=timezone.utc)
            result = {
                account: (
                    increase,
                    reduction,
                    max(
                        merged[account].get("last_source_tx", min_date),
                        merged[account].get("last_target_tx", min_date),
                    ),
                )
                for account, (increase, reduction) in result.items()
            }

        return result


class Transaction(models.Model):
    # We do not enforce that source != target because those rows are not harmful.
    source = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="transaction_source_set"
    )
    target = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="transaction_target_set"
    )
    # Amount can only be (strictly) positive
    amount = models.DecimalField(
        decimal_places=2, max_digits=8, validators=[MinValueValidator(Decimal("0.01"))]
    )
    moment = models.DateTimeField(default=now)
    description = models.CharField(max_length=1000)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="transaction_set"
    )

    objects = TransactionQuerySet.as_manager()

    # This model should not have a default ordering because that probably
    # breaks stuff like `sum_by_account`. See
    # https://stackoverflow.com/a/1341667/2373688

    def reversal(self, reverted_by: User):
        """Returns a reversal transaction for this transaction (unsaved)."""
        return Transaction(
            source=self.target,
            target=self.source,
            amount=self.amount,
            # I'm undecided between 'revert' and 'refund'.
            description=f'Refund "{self.description}"',
            created_by=reverted_by,
        )

    def __str__(self):
        return f"{self.source} -> {self.target} - {self.amount}"
