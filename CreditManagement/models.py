from django.db import models
from django.db.models import F, Q, Avg, Count, Min, Sum, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from UserDetails.models import User, Association
from Dining.models import *
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from decimal import Decimal
from datetime import datetime


# Create your models here.
class Transaction(models.Model):
    date = models.DateField(auto_now_add=True)
    source_user = models.ForeignKey(User, related_name="transaction_source", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The user giving the money")
    source_association = models.ForeignKey(Association, related_name="transaction_source", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The association giving the money")
    amount = models.DecimalField(verbose_name="Money transferred", decimal_places=2, max_digits=4, validators=[MinValueValidator(Decimal('0.01'))])
    target_user = models.ForeignKey(User, related_name="transaction_target", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The user receiving the money")
    target_association = models.ForeignKey(Association, related_name="transaction_target", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="The association recieving the money")
    description = models.CharField(default="", blank=True, max_length=50)

    def source(self):
        if self.source_association is None:
            return self.source_user
        else:
            return self.source_association

    def target(self):
        if self.target_association is None:
            return self.target_user
        else:
            return self.target_association

    def save(self, *args, **kwargs):
        # If older versions are present, retract them
        if (self.id):
            # There is an older version get it.
            old_version = Transaction.objects.get(id=self.id)
            old_source = old_version.source()
            old_target = old_version.target()

            has_source_changed = old_source != self.source()
            has_target_changed = old_target != self.target()

            amount = self.amount - old_version.amount

            with transaction.atomic():
                if has_source_changed:
                    if old_source is not None:
                        credit = old_source.get_credit_containing_instance()
                        credit.credit = F('credit') + old_version.amount
                        credit.save()
                    if self.source() is not None:
                        credit = self.source().get_credit_containing_instance()
                        credit.credit = F('credit') - self.amount
                        credit.save()
                elif amount != 0:
                    if self.source() is not None:
                        credit = self.source().get_credit_containing_instance()
                        credit.credit = F('credit') - amount
                        credit.save()

                if has_target_changed:
                    if old_target is not None:
                        credit = old_target.get_credit_containing_instance()
                        credit.credit = F('credit') - old_version.amount
                        credit.save()
                    if self.target() is not None:
                        credit = self.target().get_credit_containing_instance()
                        credit.credit = F('credit') + self.amount
                        credit.save()
                elif amount != 0:
                    if self.target() is not None:
                        credit = self.target().get_credit_containing_instance()
                        credit.credit = F('credit') + amount
                        credit.save()

                super(Transaction, self).save(*args, **kwargs)

        else:
            with transaction.atomic():
                if self.source() is not None:
                    credit = self.source().get_credit_containing_instance()
                    credit.credit = F('credit') - self.amount
                    credit.save()
                if self.target() is not None:
                    credit = self.target().get_credit_containing_instance()
                    credit.credit = F('credit') + self.amount
                    credit.save()

                super(Transaction, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            if self.source() is not None:
                credit = self.source().get_credit_containing_instance()
                credit.credit = F('credit') + self.amount
                credit.save()
            if self.target() is not None:
                credit = self.target().get_credit_containing_instance()
                credit.credit = F('credit') - self.amount
                credit.save()

            super(Transaction, self).delete(*args, **kwargs)

    def clean(self):
        if self.source() is None:
            raise ValidationError({
                'source_user': ValidationError('Either a user or association should be given as a source', code='invalid'),
                'source_association': ValidationError('Either a user or association should be given as a source', code='invalid'),
            })
        if self.target() is None:
            raise ValidationError({
                'target_user': ValidationError('Either a user or association should be given as a target', code='invalid'),
                'target_association': ValidationError('Either a user or association should be given as a target.', code='invalid'),
            })
        super(Transaction, self).clean()

    def __str__(self):
        return "€"+str(self.amount) + " " + str(self.source()) + " to " + str(self.target())


class AssociationCredit(models.Model):
    association = models.ForeignKey(Association, on_delete=models.SET_NULL, null=True)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(blank=True, null=True)
    credit = models.DecimalField(verbose_name="Credit balance", decimal_places=2, max_digits=6, default=0)
    isPayed = models.BooleanField(default=False)
    isLocked = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """
        Overwrite the save function to lock changes after closure
        :param args: not used
        :param kwargs:
        :return: None
        """
        if self.end_date is not None:
            if self.isLocked is False:
                self.isLocked = True
                super(AssociationCredit, self).save(*args, **kwargs)
                AssociationCredit(association=self.association).save()
                return

        if self.isLocked:
            super(AssociationCredit, self).save(update_fields=['isPayed'], **kwargs)
            return
        super(AssociationCredit, self).save(*args, **kwargs)

    def __str__(self):
        if self.end_date is not None:
            return self.association.name + " [" + self.start_date.strftime('%x') + " - " + self.end_date.strftime('%x') + "]"
        else:
            return self.association.name + " [" + self.start_date.strftime('%x') + " - now ]"


class UserCredit(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    credit = models.DecimalField(verbose_name="Money credit", decimal_places=2, max_digits=5, default=0)
    negative_since = models.DateField(null=True, blank=True, default=None)

    def save(self, *args, **kwargs):
        """
        An enhanced save implementation to adjust the status of the negative since counter
        """
        try:
            previous_state = UserCredit.objects.get(pk=self.pk)
        except ObjectDoesNotExist:
            previous_state = None

        if previous_state is None:
            # Model is created, it should not contain a negative credit, but just to be certain a check is implemented
            if self.credit < 0:
                self.negative_since = datetime.now().date()

            super(UserCredit, self).save(*args, **kwargs)
            return
        # save the credits
        super(UserCredit, self).save(*args, **kwargs)

        # Check for a change in negative state
        # This is done afterwards in case credit is an F-value
        self.refresh_from_db()
        # If credits are now negative
        if previous_state.negative_since is None:
            if self.credit < 0:
                self.negative_since = datetime.now().date()
                super(UserCredit, self).save(update_fields=['negative_since'])
        else:   # if credits are no longer negative
            if self.credit >= 0:
                self.negative_since = None
                super(UserCredit, self).save(update_fields=['negative_since'])
        return

    def get_current_credits(self):
        return self.credit
        # Todo: implement retrieval of pending transactions


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
