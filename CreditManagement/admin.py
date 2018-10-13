from django.contrib import admin
from CreditManagement.models import Transaction, AssociationCredit, UserCredit
from UserDetails.models import Association, UserMemberships
from datetime import datetime, timedelta

# Register your models here.
class TransactionsAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('pk', 'source', 'target', 'amount')
    list_filter = ['source_association', 'target_association', 'amount', 'date']


class AssociationCreditAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('association', 'credit', 'start_date', 'end_date')
    fields = ('association', 'credit', 'start_date', 'end_date', 'isPayed')
    readonly_fields = ('start_date',)
    list_filter = ['association', 'start_date', 'isPayed',]
    #'credit', 'association'


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
        a = UserMemberships.objects.filter(association=self.value()).values_list('related_user_id')

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

        # Find all usercredits object that adhere the given date criteria
        start_date = (datetime.now()-timedelta(days=int(self.value()))).date()
        results = UserCredit.objects.filter(negative_since__lte=start_date).values_list('pk')

        # Crosslink the given user identities with the given query
        return queryset.filter(pk__in=results)


class UserCreditAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('user', 'credit', 'is_verified')
    list_filter = [MemberOfFilter, NegativeCreditDateFilter]
    readonly_fields = ('credit','negative_since')

    def is_verified(self, obj):
        return obj.user.is_verified()
    is_verified.short_description = 'User verified?'


admin.site.register(UserCredit, UserCreditAdmin)
admin.site.register(Transaction, TransactionsAdmin)
admin.site.register(AssociationCredit, AssociationCreditAdmin)
