from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q, Avg, Count, Min, Sum, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from UserDetails.models import User, Association
from Dining.models import *
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Value, Sum, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _

from Dining.models import DiningList
from UserDetails.models import Association, User


class TransactionManager(models.Manager):
    def with_user(self, user):
        return self.filter(Q(source_user=user) | Q(target_user=user))

    def with_association(self, association):
        return self.filter(Q(source_association=association) | Q(target_association=association))


class Transaction(models.Model):
    """
    Todo: the following database constraints should be in place:

    CHECK(amount > 0),
    CHECK(source_user IS NULL OR source_association IS NULL), -- there must be at most one source
    CHECK(target_user IS NULL OR target_association IS NULL), -- there must be at most one target
    -- there must be at least a source or a target
    CHECK(NOT(source_user IS NULL AND source_association IS NULL AND target_user IS NULL AND target_association IS NULL)),

    These probably need to be inserted using custom migration files, however these are not yet in git.
    """
    moment = models.DateTimeField(auto_now_add=True)
    # We should probably add a database index to source and target (but first do profiling)
    source_user = models.ForeignKey(User, related_name="transaction_source",
                                    on_delete=models.PROTECT, null=True, blank=True)
    source_association = models.ForeignKey(Association, related_name="transaction_source", on_delete=models.PROTECT,
                                           null=True, blank=True)
    target_user = models.ForeignKey(User, related_name="transaction_target",
                                    on_delete=models.PROTECT, null=True, blank=True)
    target_association = models.ForeignKey(Association, related_name="transaction_target", on_delete=models.PROTECT,
                                           null=True, blank=True)
    amount = models.DecimalField(decimal_places=2, max_digits=16, validators=[MinValueValidator(Decimal('0.01'))])
    notes = models.CharField(max_length=200, blank=True)

    # Optional reference to the dining list that caused this transaction, for informational purposes.
    # Todo: SET_NULL is needed to make it possible to delete dining lists, however this alters a transaction.
    # To fix: remove this dependency to dining list and move it to a DiningList model which references transactions.
    dining_list = models.ForeignKey(DiningList, related_name='transactions', on_delete=models.SET_NULL, null=True,
                                    blank=True)

    objects = TransactionManager()

    def source(self):
        """
        Returns the transaction source which is a user or an association.
        """
        return self.source_user if self.source_user else self.source_association

    def target(self):
        """
        Returns the transaction target which is a user or an association.
        """
        return self.target_user if self.target_user else self.target_association

    def save(self, *args, **kwargs):
        """
        Double-checks database constraints.
        """
        assert not self.pk, "Transaction change is not allowed."
        assert self.amount > 0, "Transaction value must be positive."
        assert not (self.source_user and self.source_association), "There must be at most one source."
        assert not (self.target_user and self.target_association), "There must be at most one target."
        assert self.source() or self.target(), "There must be at least a source or a target."
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        assert False, "Transaction deletion is not allowed"

    def clean(self):
        """
        Transaction business rules.
        """

        # Balance bottom limit
        if self.source_user:
            balance = self.source_user.balance
            new_balance = balance - self.amount
            if new_balance < settings.MINIMUM_BALANCE:
                raise ValidationError(_("Balance becomes too low"))

        # Associations cannot transfer money between each other
        if self.source_association and self.target_association:
            raise ValidationError(_("Associations cannot transfer money between each other"))

    def __str__(self):
        return "{} | {} | {} → {} | {}".format(self.moment, self.amount, self.source(), self.target(), self.notes)


# Todo: this is not yet in use
class AbstractCreditQuerySet(models.QuerySet):
    source_column = None
    target_column = None

    def annotate_balance(self):
        """
        Annotates the rows with the balance value (named 'balance').
        """
        # Calculate sum of target minus sum of source

        # Filter transactions on source
        source_sum_qs = Transaction.objects.filter(**{self.source_column: OuterRef('pk')})
        # Aggregate the rows
        source_sum_qs = source_sum_qs.values(self.source_column)
        # Annotate the sum
        source_sum_qs = source_sum_qs.annotate(source_sum=Sum('amount')).values('source_sum')
        # Encapsulate in subquery
        source_sum_qs = Coalesce(Subquery(source_sum_qs), Value(0))

        # Same as above
        target_sum_qs = Transaction.objects.filter(**{self.target_column: OuterRef('pk')})
        target_sum_qs = target_sum_qs.values(self.target_column)
        target_sum_qs = target_sum_qs.annotate(target_sum=Sum('amount')).values('target_sum')
        target_sum_qs = Coalesce(Subquery(target_sum_qs), Value(0))

        # Combine
        return self.annotate(balance=target_sum_qs - source_sum_qs)


    def annotate_negative_since(self):
        raise NotImplementedError("Todo")


class UserCreditQuerySet(AbstractCreditQuerySet):
    source_column = 'source_user'
    target_column = 'target_user'


class AssociationCreditQuerySet(AbstractCreditQuerySet):
    source_column = 'source_association'
    target_column = 'target_association'


class UserWithCredit(User):
    """
    User model enhanced with credit queries.
    """
    class Meta:
        proxy = True

    objects = UserCreditQuerySet.as_manager()

    def get_balance(self):
        query = UserWithCredit.objects.filter(pk=self.pk).annotate_balance()
        return query[0].balance


class AssociationWithCredit(Association):
    """
    Association model enhanced with credit queries.
    """
    class Meta:
        proxy = True

    objects = AssociationCreditQuerySet.as_manager()

    def get_balance(self):
        query = AssociationWithCredit.objects.filter(pk=self.pk).annotate_balance()
        return query[0].balance

class AbstractTransaction(models.Model):
    # DO NOT CHANGE THIS ORDER, IT CAN CAUSE PROBLEMS IN THE UNION METHODS AT DATABASE LEVEL!
    source_user = models.ForeignKey(User, related_name="%(class)s_transaction_source", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The user giving the money")
    source_association = models.ForeignKey(Association, related_name="%(class)s_transaction_source", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The association giving the money")
    amount = models.DecimalField(verbose_name="Money transferred", decimal_places=2, max_digits=4, validators=[MinValueValidator(Decimal('0.01'))])
    target_user = models.ForeignKey(User, related_name="%(class)s_transaction_target", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The user receiving the money")
    target_association = models.ForeignKey(Association, related_name="%(class)s_transaction_target", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The association recieving the money")

    order_moment = models.DateTimeField(auto_now_add=True)
    confirm_moment = models.DateTimeField()
    description = models.CharField(default="", blank=True, max_length=50)


    class Meta:
        abstract = True

    @classmethod
    def get_children(cls):
        return [FixedTransaction, AbstractPendingTransaction]

    @classmethod
    def get_all_credits(cls, user=None, association=None):
        """
        Get all credit instances defined in its immediate children and present them as a queryset
        Accepts user as argument
        Accepts association as argument
        :return: A queryset of all credit instances
        """

        result = None
        children = cls.get_children()

        for child in children:
            if result is None:
                result = child.get_all_credits(user, association)
            else:
                result = result.union(child.get_all_credits(user, association))

        return result

    @classmethod
    def get_user_credit(cls, user):
        """
        Returns the usercredit
        :return: The current credits
        """

        result = Decimal(0.00)
        children = cls.get_children()

        # Loop over all children and get the credits
        # It is not possible to summarize get_all_credits due to the union method (it blocks it)
        for child in children:
            child_value = child.get_user_credit(user)

            if child_value:
                result += child_value

        return result

class FixedTransaction(AbstractTransaction):
    # Todo: implement CreditQuerySet as manager from Maartens branch

    @classmethod
    def get_all_credits(cls, user=None, association=None):
        # Get all objects
        queryset = cls.objects.all()
        # Filter the objects
        if user is not None:
            # Filter on user, make sure that if source_user, source_association is none
            queryset = queryset.filter(Q(source_user=user) | Q(target_user=user))
            queryset.exclude(Q(source_user=user) & ~Q(source_association=None))
        elif association is not None:
            # Filter on association
            queryset = queryset.filter(Q(source_user=user) | Q(target_user=user))

    @classmethod
    def get_user_credit(cls, user):
        # Filter transactions on source
        source_sum_qs = FixedTransaction.objects.filter(source_user=user)
        # Aggregate the rows
        source_sum_qs = source_sum_qs.aggregate(amount_sum=Coalesce(Sum('amount'), Value(0)))
        source_sum_qs = source_sum_qs['amount_sum']

        # Filter transactions on source
        target_sum_qs = FixedTransaction.objects.filter(target_user=user)
        # Aggregate the rows
        target_sum_qs = target_sum_qs.aggregate(amount_sum=Coalesce(Sum('amount'), Value(0)))
        target_sum_qs = target_sum_qs['amount_sum']

        return target_sum_qs - source_sum_qs


class AbstractPendingTransaction(AbstractTransaction):

    @classmethod
    def get_children(cls):
        return [PendingTransaction, PendingDiningTransaction]

    class Meta:
        abstract = True


class PendingTransaction(AbstractPendingTransaction):

    # Todo: implement CreditQuerySet as manager from Maartens branch

    @classmethod
    def get_all_credits(cls, user=None, association=None):
        # Get all objects
        queryset = cls.objects.all()
        # Filter the objects
        if user is not None:
            # Filter on user, make sure that if source_user, source_association is none
            queryset = queryset.filter(Q(source_user=user) | Q(target_user=user))
            queryset.exclude(Q(source_user=user) & ~Q(source_association=None))
        elif association is not None:
            # Filter on association
            queryset = queryset.filter(Q(source_association=association) | Q(target_association=association))
        return queryset

    @classmethod
    def get_user_credit(cls, user):
        # Filter transactions on source
        source_sum_qs = PendingTransaction.objects.filter(source_user=user)
        # Aggregate the rows
        source_sum_qs = source_sum_qs.aggregate(amount_sum=Coalesce(Sum('amount'), Value(0)))
        source_sum_qs = source_sum_qs['amount_sum']

        # Filter transactions on source
        target_sum_qs = PendingTransaction.objects.filter(target_user=user)
        # Aggregate the rows
        target_sum_qs = target_sum_qs.aggregate(amount_sum=Coalesce(Sum('amount'), Value(0)))
        target_sum_qs = target_sum_qs['amount_sum']

        return target_sum_qs - source_sum_qs

class PendingDiningTransaction(AbstractPendingTransaction):
    dining_identifier = "DINING"
    #todo Implement autopay

    @classmethod
    def get_all_credits(cls, user=None, association=None):
        # If queried on association, return nothing, associations can not pay dining lists
        if association:
            return PendingDiningTransaction.objects.none()

        # IMPORTANT, DO NOT MESS UP THE ORDER!
        # Changing it creates problems in the union query at database level

        PDT = PendingDiningTransaction.objects.all()
        # If there are no instances in the database, the union will result in arbitrary dicts,
        # 1 entry needs to be present in the database with no contents
        if len(PDT) == 0:
            PendingDiningTransaction(amount=42, description=cls.dining_identifier).save()
            PDT = PendingDiningTransaction.objects.all()
        none_obj = Subquery(PDT.values('target_user')[:1])
        desc_obj = Subquery(PDT.values('description')[:1])

        # Select all entries in the pending dininglists
        entries = DiningEntry.objects.filter(dining_list__pendingdininglisttracker__isnull=False)
        # Filter for the given user
        if user:
            entries = entries.filter(user=user)

        # Rename the user parameter and merge contents (user entries on each dining list)
        entries = entries.annotate(source_user=F('user'))
        entries = entries.values('dining_list', 'source_user')

        # annotate empty association object
        entries = entries.annotate(source_association=none_obj)
        # compute the total costs
        entries = entries.annotate(amount=Sum('dining_list__kitchen_cost'))

        # add the residual data
        entries = entries.annotate(target_user=none_obj)
        entries = entries.annotate(target_association=none_obj)
        entries = entries.annotate(order_moment=F('dining_list__sign_up_deadline'))
        entries = entries.annotate(confirm_moment=F('dining_list__sign_up_deadline'))
        entries = entries.annotate(description=desc_obj)

        # NOTE: The dining list is stored in the id position
        #       it is used to connect the transaction with the dining list

        # Merge the created entries with the entries in the pending dining transactions
        # Remove the unused entries from the database table
        PDT = PDT.union(entries).difference(PDT)
        # Django now treats this as a PendingDiningTransaction queryset

        return PDT

    @classmethod
    def get_user_credit(cls, user):
        # Select all entries in the pending dininglists, filter on the intended user in that dining list
        entries = DiningEntry.objects.filter(dining_list__pendingdininglisttracker__isnull=False)
        entries = entries.filter(user=user)

        # compute the total costs of the dining list
        entries = entries.aggregate(amount_sum=Coalesce(Sum('dining_list__kitchen_cost'), Value(0)))

        return -entries['amount_sum']


class PendingDiningListTracker(models.Model):
    dining_list = models.OneToOneField(DiningList, on_delete=models.CASCADE)
