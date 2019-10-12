from django.contrib import admin

from CreditManagement.models import FixedTransaction, PendingDiningListTracker, PendingDiningTransaction, \
    PendingTransaction, UserCredit
from UserDetails.models import Association, UserMembership


class MemberOfFilter(admin.SimpleListFilter):
    """Creates a filter that filters users on the association they are part of (unvalidated)."""

    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Member of association'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'associationmember'

    def lookups(self, request, model_admin):
        """Returns a list of tuples representing all the associations as displayed in the table."""
        return Association.objects.all().values_list('pk', 'name', )

    def queryset(self, request, queryset):
        """Returns the filtered querysets containing all members of the selected associations."""
        # If no selection is made, return the entire query
        if self.value() is None:
            return queryset

        # Find all members in the UserMemberships model containing the selected association
        a = UserMembership.objects.filter(association=self.value()).values_list('related_user_id')

        # Crosslink the given user identities with the given query
        return queryset.filter(user__pk__in=a)


class FixedTransactionAdmin(admin.ModelAdmin):
    list_display = ('order_moment', 'source_user', 'source_association',
                    'amount', 'target_user', 'target_association')


class PendingTransactionAdmin(admin.ModelAdmin):
    list_display = ('order_moment', 'source_user', 'source_association',
                    'amount', 'target_user', 'target_association')

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
    list_filter = [MemberOfFilter]
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
