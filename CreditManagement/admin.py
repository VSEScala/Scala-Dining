from datetime import datetime, timedelta

from django.contrib import admin

from CreditManagement.models import Transaction
from UserDetails.models import Association, UserMembership


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('moment', 'source_user', 'source_association', 'target_user', 'target_association', 'amount')
    list_filter = ('moment', 'source_association', 'target_association')
    fields = (('source_user', 'source_association'), ('target_user', 'target_association'),
              'amount', 'notes', 'dining_list')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Transaction, TransactionAdmin)


class MemberOfFilter(admin.SimpleListFilter):
    """
    Creates a filter that filters users on the association they are part of (unvalidated)
    """
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Member of association'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'associationmember'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples representing all the associations
        as displayed in the table
        """

        return Association.objects.all().values_list('pk', 'name', )

    def queryset(self, request, queryset):
        """
        Returns the filtered querysets containing all members of the selected associations
        """

        # If no selection is made, return the entire query
        if self.value() is None:
            return queryset

        # Find all members in the UserMemberships model containing the selected association
        a = UserMembership.objects.filter(association=self.value()).values_list('related_user_id')

        # Crosslink the given user identities with the given query
        return queryset.filter(user__pk__in=a)


class NegativeCreditDateFilter(admin.SimpleListFilter):
    """
    A filter that filters users on the time they've had a negative balance.
    """
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Negative credits since'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'neg_credits_since'

    neg_since_list = ((0, "Any date"),
                      (3, "Three days"),
                      (7, "One week"),
                      (30, "One month"),
                      (90, "Three months"),)

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples representing all the associations
        as displayed in the table
        """

        return self.neg_since_list

    def queryset(self, request, queryset):
        """
        Returns the filtered querysets containing all members of the selected associations
        """

        # If no selection is made, return the entire query
        if self.value() is None:
            return queryset

        # Todo: disabled due to switch to transactions
        return queryset
        # Find all usercredits object that adhere the given date criteria
        # start_date = (datetime.now() - timedelta(days=int(self.value()))).date()
        # results = UserCredit.objects.filter(negative_since__lte=start_date).values_list('pk')

        # Crosslink the given user identities with the given query
        # return queryset.filter(pk__in=results)
