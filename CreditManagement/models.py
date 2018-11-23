from django.db import models, transaction
from django.db.models import F
from UserDetails.models import User, Association
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
