from django.db import models
from django.db.models import Q, F, Value, Sum, OuterRef, Subquery, IntegerField, CharField, DecimalField
from django.db.models.functions import Coalesce

from Dining.models import DiningEntry
from UserDetails.models import User, Association


class AbstractTransactionQuerySet(models.QuerySet):
    """
    An abstract Transaction Queryset, defines base methods for filtering and balance computations
    For any model inheriting the AbstractTransaction class
    """

    def __filter_for__(self, item, source_column, target_column):
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

    def __annotate_balance__(self, items, source_column, target_column):
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
        transaction_queries = self.__filter_for__(items, source_column=source_column, target_column=target_column)

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
        return items.annotate(balance=target_sum_qs - source_sum_qs)

    def __compute_balance__(self, item, source_column, target_column):
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
        return self.__filter_for__(user, self.source_user_column, self.target_user_column)

    def filter_association(self, association):
        return self.__filter_for__(association, self.source_association_column, self.target_association_column)

    def annotate_user_balance(self):
        return self.annotate_user_balance(User.objects.all())

    def annotate_user_balance(self, users):
        return self.__annotate_balance__(users, self.source_user_column, self.target_user_column)

    def annotate_association_balance(self):
        return self.annotate_association_balance(Association.objects.all())

    def annotate_association_balance(self, association):
        return self.__annotate_balance__(association, self.source_association_column, self.target_association_column)

    def compute_user_balance(self, user):
        return self.__compute_balance__(user, self.source_user_column, self.target_user_column)

    def compute_association_balance(self, association):
        return self.__compute_balance__(association, self.source_association_column, self.target_association_column)


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

    def annotate_user_balance(self):
        return self.annotate_user_balance(User.objects.all())

    def annotate_user_balance(self, users):
        """
        Annotates the user balance behind all the users
        :param users: The users which need their balance calculated
        :return: The users with 'balance' annotated
        """
        queries = self.generate_queryset(users=users)
        return queries.__annotate_balance__(users, 'source_user', 'target_user')

    def annotate_association_balance(self):
        return self.annotate_association_balance(Association.objects.all())

    def annotate_association_balance(self, associations):
        return associations.annotate(balance=Value(0.00, output_field=DecimalField()))


    @classmethod
    def generate_queryset(cls, user=None, users=None):
        """
        Generates a query for all the Pending Dining Transactions, these can not be taken directly from the Database
        as storing it has been done elsewhere (indirectly through DiningEntry)
        :param user: A single user to filter on (more efficient if done here), can not be used if users is set
        :param users: A list of users to filter on (more efficient if done here), can not be used if user is set
        :return: The queryset of PendingDiningTransactions
        """
        if user and users:
            raise ValueError("Received both user and users with a value, expected only one of them")

        # Select all entries in the pending dininglists
        entries = DiningEntry.objects.filter(dining_list__pendingdininglisttracker__isnull=False)

        if user:
            # Filter for the given user
            entries = entries.filter(user__id=user)
        elif users:
            # Filter for the given set of users
            entries = entries.filter(user__id__in=users)

        # Rename the user parameter and merge contents (user entries on each dining list)
        entries = entries.annotate(source_user=F('user'))
        entries = entries.values('dining_list', 'source_user')

        # annotate empty association object
        entries = entries.annotate(source_association=Value(None, output_field=IntegerField()))

        # compute the total costs
        entries = entries.annotate(amount=Sum('dining_list__kitchen_cost'))

        # add the residual data
        entries = entries.annotate(target_user=Value(None, output_field=IntegerField()))
        entries = entries.annotate(target_association=Value(None, output_field=IntegerField()))
        entries = entries.annotate(order_moment=F('dining_list__sign_up_deadline'))
        entries = entries.annotate(confirm_moment=F('dining_list__sign_up_deadline'))
        entries = entries.annotate(description=Value(cls.dining_identifier, output_field=CharField()))

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