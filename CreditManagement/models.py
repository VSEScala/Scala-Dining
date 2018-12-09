from datetime import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F
from django.conf import settings

from UserDetails.models import User, Association


class TransactionManager(models.Manager):
    pass


class Transaction(models.Model):
    """

    Todo: the following database constraints should be in place:

    CHECK(amount > 0),
    CHECK(source_user IS NULL OR source_association IS NULL), -- there must be at most one source
    CHECK(target_user IS NULL OR target_association IS NULL), -- there must be at most one target
    -- there must be at least a source or a target
    CHECK(NOT(source_user IS NULL AND source_association IS NULL AND target_user IS NULL AND target_association IS NULL)),

    These probably need to be inserted using custom migrations, however these are not yet in git.
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
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Transaction deletion is not allowed")

    def __str__(self):
        return "{} | {} | {} → {} | {}".format(self.moment, self.amount, self.source(), self.target(), self.notes)


# Todo: remove
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
            return self.association.name + " [" + self.start_date.strftime('%x') + " - " + self.end_date.strftime(
                '%x') + "]"
        else:
            return self.association.name + " [" + self.start_date.strftime('%x') + " - now ]"


# Todo: remove
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
        else:  # if credits are no longer negative
            if self.credit >= 0:
                self.negative_since = None
                super(UserCredit, self).save(update_fields=['negative_since'])
        return

    def get_current_credits(self):
        return self.credit
        # Todo: implement retrieval of pending transactions
