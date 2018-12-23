from decimal import Decimal

from django.conf import settings
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
        if self.pk:
            raise ValueError("Transaction change is not allowed")
        if self.source_user and self.source_association:
            raise ValueError("There must be at most one source")
        if self.target_user and self.target_association:
            raise ValueError("There must be at most one target")
        if not self.source() and not self.target():
            raise ValueError("There must be at least a source or a target")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Transaction deletion is not allowed")

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