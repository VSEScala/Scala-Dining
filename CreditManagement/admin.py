from django.contrib import admin

from CreditManagement.models import *
from UserDetails.models import Association, UserMembership


class MemberOfFilter(admin.SimpleListFilter):
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


class HasMemberSelected(admin.SimpleListFilter):
    def lookups(self, request, model_admin):
        """
        Returns a list of tuples representing all the associations
        as displayed in the table
        """

        return [(1, "User"), (2, "Association"), (3, "None")]

    def queryset(self, request, queryset):
        """
        Returns the filtered querysets containing all members of the selected associations
        """

        if self.value() == "1":
            return queryset.filter(**{self.column_name+"_user__isnull": False})
        if self.value() == "2":
            return queryset.filter(**{self.column_name+"_association__isnull": False})
        if self.value() == "3":
            return queryset.filter(**{self.column_name+"_user__isnull": True,
                                      self.column_name+"_association__isnull": True})

        return queryset


class SelectedSource(HasMemberSelected):
    title = 'Selected source type'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'source_type'
    column_name = 'source'


class SelectedTarget(HasMemberSelected):
    title = 'Selected target type'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'target_type'
    column_name = 'target'


class NegativeCreditDateFilter(admin.SimpleListFilter):
    """
    A filter that filters users on the time they've had a negative balance.
    """
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Balance score'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'neg_credits_since'

    neg_since_list = ((1, "Positive"),
                      (2, "Negative"))

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

        if self.value() is None:
            return queryset

        try:
            value = int(self.value())
        except ValueError:
            value = None

        if value == 1:
            return queryset.filter(balance__gte=0)
        if value == 2:
            return queryset.filter(balance__lt=0)

        return queryset


class FixedTransactionAdmin(admin.ModelAdmin):
    list_display = ('order_moment', 'source', 'amount', 'target', 'description')
    list_filter = [SelectedSource, 'source_association', SelectedTarget]


class PendingTransactionAdmin(admin.ModelAdmin):
    list_display = ('order_moment', 'source', 'amount', 'target', 'description')
    list_filter = [SelectedSource, 'source_association', SelectedTarget]

    actions = ['finalise']

    @staticmethod
    def finalise(request, queryset):
        for obj in queryset:
            obj.finalise()


class PendingDiningListTrackerAdmin(admin.ModelAdmin):
    list_display = ('dining_list',)

    actions = ['finalise']

    @staticmethod
    def finalise(request, queryset):
        for obj in queryset:
            obj.finalise()


class PendingDiningTransactionAdmin(admin.ModelAdmin):
    list_display = ('order_moment', 'source_user', 'amount')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class UserCreditAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'balance_fixed', 'is_verified', 'negative_since')
    list_filter = [MemberOfFilter, NegativeCreditDateFilter]
    readonly_fields = ('negative_since',)

    def is_verified(self, obj):
        return obj.user.is_verified()
    is_verified.short_description = 'User verified?'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(FixedTransaction, FixedTransactionAdmin)
admin.site.register(PendingTransaction, PendingTransactionAdmin)
admin.site.register(PendingDiningTransaction, PendingDiningTransactionAdmin)
admin.site.register(PendingDiningListTracker, PendingDiningListTrackerAdmin)
admin.site.register(UserCredit, UserCreditAdmin)
