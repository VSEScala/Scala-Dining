from django.db import models
from django.db.models import Q, Value, Sum, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from userdetails.models import User, Association


class AbstractTransactionQuerySet(models.QuerySet):
    """An abstract Transaction Queryset, defines base methods for filtering and balance computations."""

    def _filter_for(self, item, source_column, target_column):
        """Filters the transactions for the given parameters, returns all if item is None.

        :param item: The item that needs to be filtered on, can also be a queryset
        :param source_column: The source column of the transaction
        :param target_column: The target column of the transaction
        :return: a queryset containing all contents using item, returns the entire queryset if item is None
        """
        if item is not None:
            if type(item) is models.QuerySet:
                return self.filter(Q(**{source_column + "__in": item}) | Q(**{target_column + "__in": item}))
            else:
                return self.filter(Q(**{source_column: item}) | Q(**{target_column: item}))
        return self

    def _annotate_balance(self, items, source_column, target_column, output_name="balance"):
        """Annotates the current balance to the current items in the items queryset.

        :param items: a queryset of the items that needs their credits computed
        :param source_column: The source column of the transaction
        :param target_column: The target column of the transaction
        :return: a queryset of the items with the balance annotated as balance
        """
        # Get a queryset of all useful queries
        # Theoretically this could increase speed for small usersets, but could take slightly longer
        # for querysets nearly identical to the complete dataset
        # don't know if I should keep this.
        # check if the balance column exists
        transaction_queries = self._filter_for(items, source_column=source_column, target_column=target_column)

        # Filter transactions on source
        source_sum_qs = transaction_queries.filter(**{source_column: OuterRef('pk')})
        # Aggregate the rows
        source_sum_qs = source_sum_qs.values(source_column)
        # Annotate the sum
        source_sum_qs = source_sum_qs.annotate(source_sum=Sum('amount')).values('source_sum')
        # Encapsulate in subquery
        source_sum_qs = Coalesce(Subquery(source_sum_qs), Value(0))

        # Same as above
        target_sum_qs = transaction_queries.filter(**{target_column: OuterRef('pk')})
        target_sum_qs = target_sum_qs.values(target_column)
        target_sum_qs = target_sum_qs.annotate(target_sum=Sum('amount')).values('target_sum')
        target_sum_qs = Coalesce(Subquery(target_sum_qs), Value(0))

        # Combine
        return items.annotate(**{output_name: target_sum_qs - source_sum_qs})

    def _compute_balance(self, item, source_column, target_column):
        """Returns the total credits based on the computed value from the queryset.

        :param item: either a user or an association
        :param source_column: the source column (source_user or source_association)
        :param target_column: the target column (source_user or source_association)
        :return: The total sum of all transactions
        """
        # Filter transactions on source
        source_sum_qs = self.filter(**{source_column: item})
        # Aggregate the rows
        source_sum_qs = source_sum_qs.aggregate(amount_sum=Coalesce(Sum('amount'), Value(0)))
        source_sum_qs = source_sum_qs['amount_sum']

        # Filter transactions on target
        target_sum_qs = self.filter(**{target_column: item})
        # Aggregate the rows
        target_sum_qs = target_sum_qs.aggregate(amount_sum=Coalesce(Sum('amount'), Value(0)))
        target_sum_qs = target_sum_qs['amount_sum']

        return target_sum_qs - source_sum_qs


class TransactionQuerySet(AbstractTransactionQuerySet):
    """Queryset for Transactions (both Fixed and Pending) Model."""
    source_user_column = 'source_user'
    target_user_column = 'target_user'
    source_association_column = 'source_association'
    target_association_column = 'target_association'

    def filter_user(self, user):
        return self._filter_for(user, self.source_user_column, self.target_user_column)

    def filter_association(self, association):
        return self._filter_for(association, self.source_association_column, self.target_association_column)

    def annotate_user_balance(self, users=User.objects.all(), output_name="balance"):
        return self._annotate_balance(users,
                                      self.source_user_column,
                                      self.target_user_column,
                                      output_name=output_name)

    def annotate_association_balance(self, associations=Association.objects.all(), output_name="balance"):
        return self._annotate_balance(associations,
                                      self.source_association_column,
                                      self.target_association_column,
                                      output_name=output_name)

    def compute_user_balance(self, user):
        return self._compute_balance(user, self.source_user_column, self.target_user_column)

    def compute_association_balance(self, association):
        return self._compute_balance(association, self.source_association_column, self.target_association_column)


class PendingTransactionQuerySet(TransactionQuerySet):
    def get_expired_transactions(self):
        """Returns all transactions that are expired and should be moved to Fixed Transactions."""
        return self.filter(confirm_moment__lte=timezone.now())
