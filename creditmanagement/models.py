from dining.models import *
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.utils.translation import gettext as _

from dining.models import DiningList
from userdetails.models import Association, User

from .querysets import TransactionQuerySet, DiningTransactionQuerySet, \
    PendingDiningTrackerQuerySet, PendingTransactionQuerySet

"""""""""""""""""""""""""""""""""""""""""""""
New implementation of the transaction models
"""""""""""""""""""""""""""""""""""""""""""""


class AbstractTransaction(models.Model):
    """
    Abstract model defining the Transaction models, can retrieve information from all its children
    """
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
                                 decimal_places=2, max_digits=4,
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
            raise ValidationError(_("Transaction can not have both a source user and source association."))
        if self.target_user and self.target_association:
            raise ValidationError(_("Transaction can not have both a target user and target association."))
        if self.source_user and self.source_user == self.target_user:
            raise ValidationError("Source and target user can't be the same.")
        if self.source_association and self.source_association == self.target_association:
            raise ValidationError("Source and target association can't be the same.")

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
    def get_user_balance(cls, user):
        """
        Returns the usercredit
        :return: The current credits
        """

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
        """
        Returns the usercredit
        :return: The current credits
        """

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
        """
        Returns a list of all users or associations with their respective credits
        :param users: A list of users to annotate, defaults to users if none is given
        :param associations: a list of associations to annnotate
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

        from django.db.models.functions import Cast
        sum_query = Cast(sum_query, models.FloatField())

        # annotate the results of the children in a single variable name
        result = result.annotate(**{cls.balance_annotation_name: sum_query})

        return result

    def source(self):
        return self.source_association if self.source_association else self.source_user

    def target(self):
        return self.target_association if self.target_association else self.target_user


class FixedTransaction(AbstractTransaction):
    """
    Transaction model on an immutable
    Contains all final processed transactions
    """
    objects = TransactionQuerySet.as_manager()
    balance_annotation_name = "balance_fixed"

    def save(self, *args, **kwargs):
        if self.id is None:
            self.confirm_moment = timezone.now()
            super(FixedTransaction, self).save(*args, **kwargs)

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
    def get_user_balance(cls, user):
        return cls.objects.compute_user_balance(user)

    @classmethod
    def get_association_balance(cls, association):
        """
        Compute the balance according to this model based on the given association
        :param association: The association
        :return: The balance in Decimal
        """
        return cls.objects.compute_association_balance(association)

    @classmethod
    def annotate_balance(cls, users=None, associations=None, output_name=balance_annotation_name):
        if associations:
            return cls.objects.annotate_association_balance(associations=associations, output_name=output_name)
        else:
            return cls.objects.annotate_user_balance(users=users, output_name=output_name)


class AbstractPendingTransaction(AbstractTransaction):
    """
    Abstract model for the Pending Transactions
    """
    balance_annotation_name = "balance_pending"

    class Meta:
        abstract = True

    @classmethod
    def get_children(cls):
        return [PendingTransaction, PendingDiningTransaction]

    def finalise(self):
        raise NotImplementedError()

    @classmethod
    def finalise_all_expired(cls):
        """
        Moves all pending transactions to the fixed transactions table
        :return: All new entries in the fixed transaction table
        """
        # Get all child classes
        children = cls.get_children()

        # Loop over all children, finalise them and add all retrieved items to a combined list
        result = []
        for child in children:
            result = result + child.finalise_all_expired()

        return result


class PendingTransaction(AbstractPendingTransaction):
    """
    Model for the general Pending Transactions
    """

    objects = PendingTransactionQuerySet.as_manager()
    balance_annotation_name = "balance_pending_normal"

    def clean(self):
        """
        Performs entry checks on model contents
        """
        super(PendingTransaction, self).clean()

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
            if new_balance < settings.MINIMUM_BALANCE_FOR_USER_TRANSACTION:
                raise ValidationError(_("Balance becomes too low"))

        # Associations cannot transfer money between each other
        # This works counterintuitive. There is no reason why this should be forbidden.
        # It's weird that Scala can not transfer money to associations.
        # if self.source_association and self.target_association:
        #    raise ValidationError(_("Associations cannot transfer money between each other"))

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

        return fixed_transaction

    def save(self, *args, **kwargs):
        # If no confirm moment is given, set it to the standard
        if self.confirm_moment is None:
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
    def get_user_balance(cls, user):
        return cls.objects.compute_user_balance(user)

    @classmethod
    def get_association_balance(cls, association):
        """
        Compute the balance according to this model based on the given association
        :param association: The association
        :return: The balance in Decimal
        """
        return cls.objects.compute_association_balance(association)

    @classmethod
    def annotate_balance(cls, users=None, associations=None, output_name=balance_annotation_name):
        if associations:
            return cls.objects.annotate_association_balance(associations=associations, output_name=output_name)
        else:
            return cls.objects.annotate_user_balance(users=users, output_name=output_name)


class PendingDiningTransactionManager(models.Manager):
    """
    Manager for the PendingDiningTransaction Model
    Created specially due to the different behaviour of the model (different database and model use)
    """

    @staticmethod
    def get_queryset(user=None, dining_list=None):
        return DiningTransactionQuerySet.generate_queryset(user=user, dining_list=dining_list)

    @staticmethod
    def annotate_users_balance(users, output_name=None):
        return DiningTransactionQuerySet.annotate_user_balance(users=users, output_name=output_name)

    @staticmethod
    def annotate_association_balance(associations, output_name=None):
        return DiningTransactionQuerySet.annotate_association_balance(associations=associations,
                                                                      output_name=output_name)


class PendingDiningTransaction(AbstractPendingTransaction):
    """
    Model for the Pending Dining Transactions
    Does NOT create a database, information is obtained elsewhere as specified in the manager/queryset
    """
    balance_annotation_name = "balance_pending_dining"
    objects = PendingDiningTransactionManager()

    class Meta:
        managed = False

    @classmethod
    def finalise_all_expired(cls):
        # Get all finished dining lists
        results = []
        for dining_list in PendingDiningListTracker.objects.filter_lists_expired():
            results += dining_list.finalise()
        return results

    @classmethod
    def get_all_transactions(cls, user=None, association=None):
        if association:
            # Return none, no associations can be involved in dining lists
            return cls.objects.none()
        return cls.objects.get_queryset(user=user)

    @classmethod
    def get_user_balance(cls, user):
        return cls.objects.all().compute_user_balance(user)

    @classmethod
    def get_association_balance(cls, association):
        return cls.objects.all().compute_association_balance(association)

    @classmethod
    def annotate_balance(cls, users=None, associations=None, output_name=balance_annotation_name):
        if associations:
            return cls.objects.annotate_association_balance(associations, output_name=cls.balance_annotation_name)
        else:
            return cls.objects.annotate_users_balance(users, output_name=cls.balance_annotation_name)

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

    def _get_fixedform_(self):
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
            transactions.append(dining_transaction._get_fixedform_())

        # Save the changes
        with transaction.atomic():
            for fixed_transaction in transactions:
                fixed_transaction.save()
            self.delete()

        return transactions

    @classmethod
    def finalise_to_date(cls, date):
        """
        Finalises all pending dining list transactions till the given date
        :param date: The date all tracked dining lists need to be finalised
        """
        query = cls.objects.filter_lists_for_date(date)
        for pending_dining_list_tracker in query:
            pending_dining_list_tracker.finalise()


"""""""""""""""""""""""""""""""""""""""""""""
New implemented User and Association Views
"""""""""""""""""""""""""""""""""""""""""""""


class UserCredit(models.Model):
    """
    User credit model, implemented as Database VIEW (see migrations/usercredit_view.py)
    """
    user = models.OneToOneField(User, primary_key=True,
                                db_column='id',
                                on_delete=models.DO_NOTHING)
    balance = models.DecimalField(blank=True, null=True,
                                  db_column=AbstractTransaction.balance_annotation_name,
                                  decimal_places=2,
                                  max_digits=6)
    balance_fixed = models.DecimalField(blank=True,
                                        null=True,
                                        db_column=FixedTransaction.balance_annotation_name,
                                        decimal_places=2,
                                        max_digits=6)

    def negative_since(self):
        """
        Compute the date from the balance_fixed table when the users balance has become negative
        :return: The date when the users balance became negative
        """
        balance = self.balance_fixed
        if balance >= 0:
            # balance is already positive, return nothing
            return None

        # Loop over all transactions from new to old, reverse its balance
        transactions = FixedTransaction.get_all_transactions(user=self.user).order_by('-order_moment')
        for fixed_transaction in transactions:
            balance += fixed_transaction.amount
            # If balance is positive now, return the current transaction date
            if balance >= 0:
                return fixed_transaction.order_moment

        # This should not be reached, it would indicate that the starting balance was below 0
        raise RuntimeError("Balance started as negative, negative_since could not be computed")

    @classmethod
    def view(cls):
        """
        This method returns the SQL string that creates the view
        """

        qs = AbstractTransaction.annotate_balance(users=User.objects.all()). \
            values('id', AbstractTransaction.balance_annotation_name, FixedTransaction.balance_annotation_name)
        return str(qs.query)
