from Dining.models import *
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from Dining.models import DiningList
from UserDetails.models import Association, User
from .querysets import TransactionQuerySet, DiningTransactionQuerySet, PendingDiningTrackerQuerySet


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


class UserWithCredit(User):
    """
    User model enhanced with credit queries.
    """
    class Meta:
        proxy = True



    def get_balance(self):
        return -119


class AssociationWithCredit(Association):
    """
    Association model enhanced with credit queries.
    """
    class Meta:
        proxy = True

    def get_balance(self):
        return -121


"""""""""""""""""""""""""""""""""""""""""""""
New implementation of the transaction models
"""""""""""""""""""""""""""""""""""""""""""""


class AbstractTransaction(models.Model):
    """
    Abstract model defining the Transaction models, can retrieve information from all its children
    """
    # DO NOT CHANGE THIS ORDER, IT CAN CAUSE PROBLEMS IN THE UNION METHODS AT DATABASE LEVEL!
    source_user = models.ForeignKey(User, related_name="%(class)s_transaction_source", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The user giving the money")
    source_association = models.ForeignKey(Association, related_name="%(class)s_transaction_source", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The association giving the money")
    amount = models.DecimalField(verbose_name="Money transferred", decimal_places=2, max_digits=4, validators=[MinValueValidator(Decimal('0.01'))])
    target_user = models.ForeignKey(User, related_name="%(class)s_transaction_target", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The user receiving the money")
    target_association = models.ForeignKey(Association, related_name="%(class)s_transaction_target", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The association recieving the money")

    order_moment = models.DateTimeField(default=datetime.now)
    confirm_moment = models.DateTimeField(default=datetime.now)
    description = models.CharField(default="", blank=True, max_length=50)

    class Meta:
        abstract = True

    @classmethod
    def get_children(cls):
        """
        Get all child classes that need to be combined
        :return: Its child classes
        """
        return [FixedTransaction, AbstractPendingTransaction]

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """
        Get all credit instances defined in its immediate children and present them as a queryset
        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        :return: A queryset of all credit instances
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

    @classmethod
    def get_users_credits(cls, users):
        """
        Returns a list of all users with their respective credits
        :return: The current credits of all givn users
        """
        # Todo, compute this
        raise NotImplementedError


class FixedTransaction(AbstractTransaction):
    """
    Transaction model on an immutable (TODO) Database
    Contains all final processed transactions
    """
    objects = TransactionQuerySet.as_manager()


    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """
        Get all credit instances defined in its immediate children and present them as a queryset
        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        :return: A queryset of all credit instances
        """
        # Get all objects
        return cls.objects.filter_user(user).filter_association(association)

    @classmethod
    def get_user_credit(cls, user):
        return cls.objects.compute_user_balance(user)

    @classmethod
    def get_association_credit(cls, association):
        """
        Compute the balance according to this model based on the given association
        :param association: The association
        :return: The balance in Decimal
        """
        return cls.objects.compute_association_balance(association)


class AbstractPendingTransaction(AbstractTransaction):
    """
    Abstract model for the Pending Transactions
    """

    @classmethod
    def get_children(cls):
        return [PendingTransaction, PendingDiningTransaction]

    def finalise(self):
        raise NotImplementedError()

    class Meta:
        abstract = True


class PendingTransaction(AbstractPendingTransaction):
    """
    Model for the general Pending Transactions
    """

    objects = TransactionQuerySet.as_manager()

    def finalise(self):
        """
        Moves the pending transaction over as a fixed transaction
        """
        # Create the fixed database entry
        fixed_transaction = FixedTransaction(source_user=self.source_user, source_association=self.source_association,
                                             target_user=self.target_user, target_association=self.target_association,
                                             amount=self.amount,
                                             order_moment=self.order_moment, description=self.description)
        # 'Move' the transaction to the other database
        with transaction.atomic():
            self.delete()
            fixed_transaction.save()


    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        """
        Get all credit instances defined in its immediate children and present them as a queryset
        :param user: The user(s) that need to be part of the transactions
                     Can be single instance or queryset of instances
        :param association: The association(s) that need to be part of the transactions.
                            Can be single instance or queryset of instances
        :return: A queryset of all credit instances
        """
        # Get all objects
        return cls.objects.filter_user(user).filter_association(association)

    @classmethod
    def get_user_credit(cls, user):
        return cls.objects.compute_user_balance(user)

    @classmethod
    def get_association_credit(cls, association):
        """
        Compute the balance according to this model based on the given association
        :param association: The association
        :return: The balance in Decimal
        """
        return cls.objects.compute_association_balance(association)


class PendingDiningTransactionManager(models.Manager):
    """
    Manager for the PendingDiningTransaction Model
    Created specially due to the different behaviour of the model (different database and model use)
    """
    def get_queryset(self, user=None, dining_list=None):
        return DiningTransactionQuerySet.generate_queryset(user=user, dining_list=dining_list)


class PendingDiningTransaction(AbstractPendingTransaction):
    """
    Model for the Pending Dining Transactions
    Does NOT create a database, information is obtained elsewhere as specified in the manager/queryset
    """

    objects = PendingDiningTransactionManager()

    class Meta:
        managed = False

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        if association:
            # Return none, no associations can be involved in dining lists
            return cls.objects.none()
        return cls.objects.get_queryset(user=user)

    @classmethod
    def get_user_credit(cls, user):
        return cls.objects.all().compute_user_balance(user)

    @classmethod
    def get_association_credit(cls, association):
        """
        Compute the balance according to this model based on the given association
        :param association: The association
        :return: The balance in Decimal
        """
        return Decimal(0.00)

    def finalise(self):
        raise NotImplementedError("PendingDiningTransactions are read-only")

    def __get_fixedform__(self):
        return FixedTransaction(source_user=self.source_user, source_association=self.source_association,
                                target_user=self.target_user, target_association=self.target_association,
                                amount=self.amount,
                                order_moment=self.order_moment, description=self.description)


class PendingDiningListTracker(models.Model):
    """
    Model to track all Dining Lists that are pending.
    Used for creating Pending Dining Transactions
    """
    dining_list = models.OneToOneField(DiningList, on_delete=models.CASCADE)

    objects = PendingDiningTrackerQuerySet.as_manager()

    def finalise(self):
        # Generate the initial list
        transactions = []

        # Get all corresponding dining transactions
        # loop over all items and make the transactions
        for dining_transaction in PendingDiningTransaction.objects.get_queryset(dining_list=self.dining_list):
            transactions.append(dining_transaction.__get_fixedform__())

        # Save the changes
        with transaction.atomic():
            for fixed_transaction in transactions:
                print("A5")
                print(fixed_transaction)
                fixed_transaction.save()
            self.delete()

    @classmethod
    def finalise_to_date(cls, date):
        """
        Finalises all pending dining list transactions till the given date
        :param date: The date all tracked dining lists need to be finalised
        """
        query = cls.objects.filter_lists_for_date(date)
        for pendingdininglist_tracker in query:
            pendingdininglist_tracker.finalise()
