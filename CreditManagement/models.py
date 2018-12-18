from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from Dining.models import DiningList
from UserDetails.models import Association


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
    source_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="transaction_source",
                                    on_delete=models.PROTECT, null=True, blank=True)
    source_association = models.ForeignKey(Association, related_name="transaction_source", on_delete=models.PROTECT,
                                           null=True, blank=True)
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="transaction_target",
                                    on_delete=models.PROTECT, null=True, blank=True)
    target_association = models.ForeignKey(Association, related_name="transaction_target", on_delete=models.PROTECT,
                                           null=True, blank=True)
    amount = models.DecimalField(decimal_places=2, max_digits=16, validators=[MinValueValidator(Decimal('0.01'))])
    notes = models.CharField(max_length=200, blank=True)

    # Optional reference to the dining list that caused this transaction, for informational purposes.
    # Todo: SET_NULL is needed to make it possible to delete dining lists, however this alters a transaction.
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
        if self.pk:
            raise ValueError("Transaction change is not allowed")

        # Double-check database constraints
        if self.source_user and self.source_association:
            raise ValueError("There must be at most one source")
        if self.target_user and self.target_association:
            raise ValueError("There must be at most one target")
        if not self.source() and not self.target():
            raise ValueError("There must be at least a source or a target")

        # Balance bottom limit
        if self.source_user:
            balance = self.source_user.balance
            new_balance = balance - self.amount
            if new_balance < settings.MINIMUM_BALANCE:
                raise ValueError("Balance becomes too low")

        # Associations cannot transfer money between each other
        if self.source_association and self.target_association:
            raise ValueError("Associations cannot transfer money between each other")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Transaction deletion is not allowed")

    def __str__(self):
        return "{} | {} | {} → {} | {}".format(self.moment, self.amount, self.source(), self.target(), self.notes)


# Todo: remove
class AssociationCredit():
    pass


"""
class AssociationCredit(models.Model):
    association = models.ForeignKey(Association, on_delete=models.SET_NULL, null=True)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(blank=True, null=True)
    credit = models.DecimalField(verbose_name="Credit balance", decimal_places=2, max_digits=6, default=0)
    isPayed = models.BooleanField(default=False)
    isLocked = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """"""
        Overwrite the save function to lock changes after closure
        :param args: not used
        :param kwargs:
        :return: None
        """"""
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
            return self.association.name + " [" + self.start_date.strftime('%x') + " - " + self.end_date.strftime(
                '%x') + "]"
        else:
            return self.association.name + " [" + self.start_date.strftime('%x') + " - now ]"
"""

# Todo: remove
"""
class UserCredit(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    credit = models.DecimalField(verbose_name="Money credit", decimal_places=2, max_digits=5, default=0)
    negative_since = models.DateField(null=True, blank=True, default=None)

    def save(self, *args, **kwargs):
        """"""
        An enhanced save implementation to adjust the status of the negative since counter
        """"""
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
        else:  # if credits are no longer negative
            if self.credit >= 0:
                self.negative_since = None
                super(UserCredit, self).save(update_fields=['negative_since'])
        return

    def get_current_credits(self):
        return self.credit
        # Todo: implement retrieval of pending transactions

"""
