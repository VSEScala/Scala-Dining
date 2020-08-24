from datetime import datetime
from decimal import Decimal
from typing import Union, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, QuerySet, Sum, Q
from django.db.models.functions import Cast
from django.utils import timezone

from creditmanagement.querysets import TransactionQuerySet, PendingTransactionQuerySet
from userdetails.models import Association, User


class AbstractTransaction(models.Model):
    """Abstract model defining the Transaction models, can retrieve information from all its children."""

    # DO NOT CHANGE THIS ORDER, IT CAN CAUSE PROBLEMS IN THE UNION METHODS AT DATABASE LEVEL!
    source_user = models.ForeignKey(User, related_name="%(class)s_transaction_source",
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    verbose_name="The user giving the money")
    source_association = models.ForeignKey(Association, related_name="%(class)s_transaction_source",
                                           on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           verbose_name="The association giving the money")
    amount = models.DecimalField(verbose_name="Money transferred",
                                 decimal_places=2, max_digits=5,
                                 validators=[MinValueValidator(Decimal('0.01'))])
    target_user = models.ForeignKey(User, related_name="%(class)s_transaction_target",
                                    on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    verbose_name="The user receiving the money")
    target_association = models.ForeignKey(Association, related_name="%(class)s_transaction_target",
                                           on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           verbose_name="The association recieving the money")

    order_moment = models.DateTimeField(default=timezone.now)
    confirm_moment = models.DateTimeField(default=timezone.now, blank=True)
    description = models.CharField(default="", blank=True, max_length=50)

    balance_annotation_name = "balance"

    class Meta:
        abstract = True

    def clean(self):
        if self.source_user and self.source_association:
            raise ValidationError("Transaction can not have both a source user and source association.")
        if self.target_user and self.target_association:
            raise ValidationError("Transaction can not have both a target user and target association.")
        if self.source_user and self.source_user == self.target_user:
            raise ValidationError("Source and target user can't be the same.")
        if self.source_association and self.source_association == self.target_association:
            raise ValidationError("Source and target association can't be the same.")

    @classmethod
    def get_children(cls):
        """Returns all child classes that need to be combined."""
        return [FixedTransaction, AbstractPendingTransaction]

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """Gets all credit instances defined in its immediate children and present them as a queryset.

        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        """
        result = None
        # Get all child classes
        children = cls.get_children()

        # Loop over all children, get their respective transaction queries, union the transaction queries
        for child in children:
            if result is None:
                result = child.get_all_transactions(user, association)
            else:
                result = result.union(child.get_all_transactions(user, association))

        return result

    @classmethod
    def get_user_balance(cls, user):
        """Returns the user balance."""
        result = Decimal(0.00)
        children = cls.get_children()

        # Loop over all children and get the credits
        # It is not possible to summarize get_all_credits due to the union method (it blocks it)
        for child in children:
            child_value = child.get_user_balance(user)

            if child_value:
                result += child_value

        return result.quantize(Decimal('.00'))

    @classmethod
    def get_association_balance(cls, association):
        """Returns the association balance."""
        result = Decimal('0.00')
        children = cls.get_children()

        # Loop over all children and get the credits
        # It is not possible to summarize get_all_credits due to the union method (it blocks it)
        for child in children:
            child_value = child.get_association_balance(association)

            if child_value:
                result += child_value

        return result.quantize(Decimal('.00'))

    @classmethod
    def annotate_balance(cls, users=None, associations=None):
        """Returns a list of all users or associations with their respective credits.

        :param users: A list of users to annotate, defaults to users if none is given
        :param associations: a list of associations to annotate
        :return: The list annotated with 'balance'
        """
        if users is not None and associations is not None:
            raise ValueError("Either users or associations need to have a value, not both")

        # Set the query result
        if associations:
            result = associations
            q_type = "associations"
        else:
            # If users is none, the result becomes a list of all users automatically (set in query retrieval)
            result = users
            q_type = "users"

        # Get all child classes
        children = cls.get_children()

        # Loop over all children, get their respective transaction queries, union the transaction queries
        for child in children:
            result = child.annotate_balance(**{q_type: result})

        # Get the annotated name values of its immediate children
        sum_query = None
        for child in children:
            # If sumquery is not yet defined, define it, otherwise add add it to the query
            if sum_query:
                sum_query += F(child.balance_annotation_name)
            else:
                sum_query = F(child.balance_annotation_name)

        sum_query = Cast(sum_query, models.FloatField())

        # annotate the results of the children in a single variable name
        result = result.annotate(**{cls.balance_annotation_name: sum_query})

        return result

    def source(self):
        return self.source_association if self.source_association else self.source_user

    def target(self):
        return self.target_association if self.target_association else self.target_user


class FixedTransaction(AbstractTransaction):
    """Transaction model for immutable final transactions."""

    objects = TransactionQuerySet.as_manager()
    balance_annotation_name = "balance_fixed"

    def save(self, *args, **kwargs):
        if self.id is None:
            self.confirm_moment = timezone.now()
            super(FixedTransaction, self).save(*args, **kwargs)

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """Get all credit instances defined in its immediate children and present them as a queryset.

        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        :return: A queryset of all credit instances
        """
        # Get all objects
        return cls.objects.filter_user(user).filter_association(association)

    @classmethod
    def get_user_balance(cls, user):
        return cls.objects.compute_user_balance(user)

    @classmethod
    def get_association_balance(cls, association: Association) -> Decimal:
        """Compute the balance according to this model based on the given association."""
        return cls.objects.compute_association_balance(association)

    @classmethod
    def annotate_balance(cls, users=None, associations=None, output_name=balance_annotation_name):
        if associations:
            return cls.objects.annotate_association_balance(associations=associations, output_name=output_name)
        else:
            return cls.objects.annotate_user_balance(users=users, output_name=output_name)


class AbstractPendingTransaction(AbstractTransaction):
    balance_annotation_name = "balance_pending"

    class Meta:
        abstract = True

    @classmethod
    def get_children(cls):
        return [PendingTransaction]

    def finalise(self):
        raise NotImplementedError()

    @classmethod
    def finalise_all_expired(cls):
        """Moves all pending transactions to the fixed transactions table.

        Returns:
            The new entries that were added to the fixed transactions table.
        """
        # Get all child classes
        children = cls.get_children()

        # Loop over all children, finalise them and add all retrieved items to a combined list
        result = []
        for child in children:
            result = result + child.finalise_all_expired()

        return result


class PendingTransaction(AbstractPendingTransaction):
    objects = PendingTransactionQuerySet.as_manager()
    balance_annotation_name = "balance_pending_normal"

    def clean(self):
        """Performs entry checks on model contents."""
        super().clean()

        # Check whether balance does not exceed set limit on balance
        # Checked here as this is primary user interaction. Check in fixed introduces possible problems where old
        # entries are not yet removed resulting in new fixed entries not allowed
        if self.source_user:
            balance = AbstractTransaction.get_user_balance(self.source_user)
            # If the object is being altered instead of created, take difference into account
            if self.pk:
                change = self.amount - self.objects.get(id=self.id).amount
            else:
                change = self.amount
            new_balance = balance - change
            if new_balance < Decimal('0.00'):
                raise ValidationError("Balance becomes too low")

    def finalise(self):
        """Moves the pending transaction over as a fixed transaction."""
        # Create the fixed database entry
        fixed_transaction = FixedTransaction(source_user=self.source_user, source_association=self.source_association,
                                             target_user=self.target_user, target_association=self.target_association,
                                             amount=self.amount,
                                             order_moment=self.order_moment, description=self.description)
        # Move the transaction to the other database
        with transaction.atomic():
            self.delete()
            fixed_transaction.save()

        return fixed_transaction

    def save(self, *args, **kwargs):
        # If no confirm moment is given, set it to the standard
        if not self.confirm_moment:
            self.confirm_moment = self.order_moment + settings.TRANSACTION_PENDING_DURATION

        super(PendingTransaction, self).save(*args, **kwargs)

    @classmethod
    def finalise_all_expired(cls):
        # Get all finalised items
        expired_transactions = cls.objects.get_expired_transactions()
        new_transactions = []
        for transaction_obj in expired_transactions:
            # finalise transaction
            new_transactions.append(transaction_obj.finalise())

        return new_transactions

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """Get all credit instances defined in its immediate children and present them as a queryset.

        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        """
        # Get all objects
        return cls.objects.filter_user(user).filter_association(association)

    @classmethod
    def get_user_balance(cls, user):
        return cls.objects.compute_user_balance(user)

    @classmethod
    def get_association_balance(cls, association) -> Decimal:
        """Compute the balance according to this model based on the given association."""
        return cls.objects.compute_association_balance(association)

    @classmethod
    def annotate_balance(cls, users=None, associations=None, output_name=balance_annotation_name):
        if associations:
            return cls.objects.annotate_association_balance(associations=associations, output_name=output_name)
        else:
            return cls.objects.annotate_user_balance(users=users, output_name=output_name)


class Account(models.Model):
    """Money account which can be used as a transaction source or target."""

    # An account can only have one of user or association or special
    user = models.OneToOneField(User, on_delete=models.PROTECT, null=True)
    association = models.OneToOneField(Association, on_delete=models.PROTECT, null=True)

    # We can have special accounts which are not linked to a user or association,
    #  e.g. an account where the kitchen payments can be sent to.

    # (The special accounts listed here are automatically created using a receiver.)
    SPECIAL_ACCOUNTS = [
        # Account which receives the kitchen payments
        # The balance indicates the money that is payed for kitchen usage (minus optional withdraws)
        ('kitchen_cost', 'Kitchen cost'),

        # Generic account, if source/target is unknown
        # All transactions in the older version that didn't have a source use this account!
        # But the account is too general so it's probably better to never use this for new transactions
        # and always use a more specific account.
        ('generic', 'Unspecified'),
    ]
    special = models.CharField(max_length=30, unique=True, null=True, default=None, choices=SPECIAL_ACCOUNTS)

    def get_balance(self) -> Decimal:
        tx = Transaction.objects.filter_valid()
        # 2 separate queries for the source and target sums
        # If there are no rows, the value will be made 0.00
        source_sum = tx.filter(source=self).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
        target_sum = tx.filter(target=self).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
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


class TransactionQuerySet2(QuerySet):
    def filter_valid(self):
        """Filters transactions that have not been cancelled."""
        return self.filter(cancelled__isnull=True)

    def filter_account(self, account: Account):
        """Filters transactions that have the given account as source or target."""
        return self.filter(Q(source=account) | Q(target=account))


class Transaction(models.Model):
    # We do not enforce that source != target because those rows are not harmful,
    #  balance is not affected when source == target.
    source = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transaction_source_set')
    target = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transaction_target_set')
    # Amount can only be (strictly) positive
    amount = models.DecimalField(decimal_places=2, max_digits=8, validators=[MinValueValidator(Decimal('0.01'))])
    moment = models.DateTimeField(default=timezone.now)
    description = models.CharField(max_length=150)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='transaction_set')

    # Implementation note on cancellation: instead of an extra 'cancelled'
    # column we could also write a method that creates a new
    # transaction that reverses this transaction. In that case however it
    # is not possible to check whether a transaction is already cancelled.
    cancelled = models.DateTimeField(null=True)
    cancelled_by = models.ForeignKey(User,
                                     on_delete=models.PROTECT,
                                     null=True,
                                     related_name='transaction_cancelled_set')

    objects = TransactionQuerySet2.as_manager()

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
