from django.db import models
from django.db.models import Q, F, Value, Sum, OuterRef, Subquery, ExpressionWrapper, Count
from django.db.models.functions import Coalesce, Cast

from Dining.models import DiningEntry, DiningList
from UserDetails.models import User, Association


class AbstractTransactionQuerySet(models.QuerySet):
    """
    An abstract Transaction Queryset, defines base methods for filtering and balance computations
    For any model inheriting the AbstractTransaction class
    """

    def _filter_for_(self, item, source_column, target_column):
        """
        Filter the transactions for the given paramater, returns all if item is None
        :param item: The item that needs to be filtered on, can also be a queryset
        :param source_column: The source column of the transaction
        :param target_column: The target column of the transaction
        :return: a queryset containing all contents using item, returns the entire queryset if item is None
        """
        if item:
            if type(item) is models.QuerySet:
                return self.filter(Q(**{source_column+"__in": item}) |
                                   Q(**{target_column+"__in": item}))
            else:
                return self.filter(Q(**{source_column: item}) |
                                   Q(**{target_column: item}))
        return self

    def _annotate_balance_(self, items, source_column, target_column, output_name="balance"):
        """
        Annotates the current balance to the current items in the items queryset
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
        transaction_queries = self._filter_for_(items, source_column=source_column, target_column=target_column)

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

    def _compute_balance_(self, item, source_column, target_column):
        """
        Returns the total credits based on the computed value from the queryset
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
    """
    Queryset for Transactions (both Fixed and Pending) Model
    """
    source_user_column = 'source_user'
    target_user_column = 'target_user'
    source_association_column = 'source_association'
    target_association_column = 'target_association'

    def filter_user(self, user):
        return self._filter_for_(user, self.source_user_column, self.target_user_column)

    def filter_association(self, association):
        return self._filter_for_(association, self.source_association_column, self.target_association_column)

    def annotate_user_balance(self, users=User.objects.all(), output_name="balance"):
        return self._annotate_balance_(users,
                                       self.source_user_column,
                                       self.target_user_column,
                                       output_name=output_name)

    def annotate_association_balance(self, associations=Association.objects.all(), output_name="balance"):
        return self._annotate_balance_(associations,
                                       self.source_association_column,
                                       self.target_association_column,
                                       output_name=output_name)

    def compute_user_balance(self, user):
        return self._compute_balance_(user, self.source_user_column, self.target_user_column)

    def compute_association_balance(self, association):
        return self._compute_balance_(association, self.source_association_column, self.target_association_column)


class DiningTransactionQuerySet(AbstractTransactionQuerySet):
    """
    Queryset for the DiningTransaction, uses special implementation to 'imitate' a working database model.
    """
    dining_identifier = "DINING"

    def compute_user_balance(self, user):
        # Select all entries in the pending dininglists, filter on the intended user in that dining list
        entries = DiningEntry.objects.filter(dining_list__pendingdininglisttracker__isnull=False)
        entries = entries.filter(user=user)

        # compute the total costs of the dining list
        entries = entries.aggregate(amount_sum=Coalesce(Sum('dining_list__kitchen_cost'), Value(0)))

        return -entries['amount_sum']

    def compute_association_balance(self, association):
        # associations can not pay for dining lists
        return 0

    @classmethod
    def annotate_user_balance(cls, users=User.objects.all(), output_name="balance"):
        """
        Annotates the user balance behind all the users
        :param users: The users which need their balance calculated
        :return: The users with 'balance' annotated
        """
        # Select all entries in the pending dininglists, filter on the intended user in that dining list
        entries = DiningEntry.objects.filter(dining_list__pendingdininglisttracker__isnull=False)

        target_sum_qs = entries.filter(user=OuterRef('pk'))
        target_sum_qs = target_sum_qs.values('user')
        target_sum_qs = target_sum_qs.annotate(kitchen_cost=F('dining_list__kitchen_cost'))
        target_sum_qs = target_sum_qs.annotate(total_cost=Coalesce(Sum('kitchen_cost'), Value(0))).values('total_cost')
        target_sum_qs = Coalesce(Subquery(target_sum_qs), Value(0))

        users = users.annotate(**{output_name: - Cast(target_sum_qs, models.FloatField())})

        # DIT HEEFT ME ZO VEEL MEER GEDOE GEGEVEN AAARGH NIET NORMAAL
        # Uiteindelijk gefixed met de Cast, daar zat het probleem, maar GVD dit was een zeer frustrerend stukje code
        # Dus ik claim hier even mijn credit
        # Wouter

        return users

    @classmethod
    def annotate_association_balance(cls, associations=Association.objects.all(), output_name="balance"):
        return associations.annotate(**{output_name: -Value(0.00, output_field=models.FloatField())})

    @staticmethod
    def _filter_entries_(entries, user=None, dining_list=None):
        """
        Filters the Dining Entries on the given users and/or dining lists
        :param entries: The dining entries model
        :param user: The user(s) that needs to be kept in (can be single instance or query)
        :param dining_list: The dining_list to be kept in (can be single instance or query)
        :return: the filtered entries Query
        """
        if user:
            if type(user) is models.QuerySet:
                # Filter for the given set of users
                entries = entries.filter(user__id__in=user)
            else:
                # Filter for the given user
                entries = entries.filter(user=user)

        if dining_list:
            if type(dining_list) is models.QuerySet:
                # Filter for the given set of users
                entries = entries.filter(dining_list__id__in=dining_list)
            else:
                # Filter for the given user
                entries = entries.filter(dining_list=dining_list)

        return entries

    @classmethod
    def generate_queryset(cls, user=None, dining_list=None):
        """
        Generates a query for all the Pending Dining Transactions, these can not be taken directly from the Database
        as storing it has been done elsewhere (indirectly through DiningEntry)
        :param user: The user(s) that needs to be part of the set. Can be single instance or Query of instances
        :param dining_list: The dining list(s) that needs to be part of the set. Can be single instance or Query of instances
        :return: The queryset of PendingDiningTransactions
        """
        # Select all entries in the pending dininglists
        entries = DiningEntry.objects.filter(dining_list__pendingdininglisttracker__isnull=False)
        entries = DiningTransactionQuerySet._filter_entries_(entries, user=user, dining_list=dining_list)

        # Rename the user parameter and merge contents (user entries on each dining list)
        entries = entries.annotate(source_user=F('user'))
        entries = entries.values('dining_list', 'source_user')

        # annotate empty association object
        entries = entries.annotate(source_association=Value(None, output_field=models.IntegerField()))

        # compute the total costs
        entries = entries.annotate(amount=Sum('dining_list__kitchen_cost'))

        # add the residual data
        entries = entries.annotate(target_user=Value(None, output_field=models.IntegerField()))
        entries = entries.annotate(target_association=Value(None, output_field=models.IntegerField()))
        entries = entries.annotate(order_moment=F('dining_list__sign_up_deadline'))
        entries = entries.annotate(confirm_moment=F('dining_list__sign_up_deadline'))
        entries = entries.annotate(description=Value(cls.dining_identifier, output_field=models.CharField()))

        # Treat the queryset as a queryset  from the given class
        from CreditManagement.models import PendingDiningTransaction
        return cls.set_queryset_to_class_type(entries, PendingDiningTransaction)

    @staticmethod
    def set_queryset_to_class_type(qs, class_name):
        """
        Adjusts the queryset to the given class type
        :param qs: the queryset
        :param class_name: the class name of the items in the queryset
        :return: the new queryset with the contents treated as the given class type
        """
        # Below code heavily inspired by the _combinator_query method in the QuerySet
        # Current implementation relies on an empty set of the class being merged with the new contents while
        # not keeping the old query (which is empty)

        # Clone the query to inherit the select list and everything
        new_qs = DiningTransactionQuerySet(model=class_name)
        # Clear limits and ordering so they can be reapplied
        new_qs.query.clear_ordering(True)
        new_qs.query.clear_limits()
        new_qs.query.combined_queries = tuple([qs.query])
        new_qs.query.combinator = 'union'
        return new_qs


class PendingDiningTrackerQuerySet(models.QuerySet):

    def filter_lists_expired(self):
        """
        Filt the trackenQuery for lists that have expired (i.e. are no longer adjustable)
        :return:
        """
        from django.utils import timezone
        return self.filter_lists_for_date(timezone.now().date())

    def filter_lists_for_date(self, date):
        """
        Returns all lists which have an editable state older than the given date
        :param date: The date that needs to be checked
        :return: A QuerySet consisting of Trackers linking to lists that are no longer editable on the given date
        """
        return self.annotate(
            # Wrap in an Expression to allow additons between variables
            lockdate=ExpressionWrapper(
                # Add the dining list date and the adjustable parameter
                F('dining_list__date') + F('dining_list__adjustable_duration'),
                output_field=models.DateField()
            )).filter(lockdate__lt=date)



