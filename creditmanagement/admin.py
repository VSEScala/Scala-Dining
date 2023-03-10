from django.contrib import admin
from django.db.models import Q

from creditmanagement.models import Account, Transaction


class AccountTypeListFilter(admin.SimpleListFilter):
    """Allows filtering on account type which is either user, association or special."""

    title = 'account type'  # (displayed in side bar)
    parameter_name = 'type'  # (used in URL query)

    # Queries can be overridden in a subclass
    user_query = Q(user__isnull=False)
    association_query = Q(association__isnull=False)
    special_query = Q(special__isnull=False)

    def lookups(self, request, model_admin):
        # First element is URL param, second element is display value
        return (
            ('user', "User"),
            ('association', "Association"),
            ('special', "Special"),
        )

    def queryset(self, request, queryset):
        if self.value() == 'user':
            return queryset.filter(self.user_query)
        if self.value() == 'association':
            return queryset.filter(self.association_query)
        if self.value() == 'special':
            return queryset.filter(self.special_query)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """The account admin enables viewing of accounts with their balance.

    Adding or deleting accounts in the back-end is allowed and is not very
    risky (only accounts with no transactions can be deleted). _Changing_ an
    account however is *very risky* thus should never be possible, because then
    you could change the user or association linked to the account.
    """

    ordering = ('special', 'association__name', 'user__first_name', 'user__last_name')
    list_display = ('__str__', 'get_balance', 'negative_since')
    list_filter = (AccountTypeListFilter,)
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'association__name', 'special')

    def has_change_permission(self, request, obj=None):
        return False


class SourceTypeListFilter(AccountTypeListFilter):
    """Allows filtering on the source account type."""
    title = "source account type"
    parameter_name = 'source_type'
    user_query = Q(source__user__isnull=False)
    association_query = Q(source__association__isnull=False)
    special_query = Q(source__special__isnull=False)


class TargetTypeListFilter(AccountTypeListFilter):
    """Allows filtering on the target account type."""
    title = "target account type"
    parameter_name = 'target_type'
    user_query = Q(target__user__isnull=False)
    association_query = Q(target__association__isnull=False)
    special_query = Q(target__special__isnull=False)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """The transaction admin enables viewing transactions and creating new transactions."""

    ordering = ('-moment',)
    list_display = ('moment', 'source', 'target', 'amount', 'description')
    list_filter = (SourceTypeListFilter, TargetTypeListFilter)

    fields = ('source', 'target', 'amount', 'moment', 'description', 'created_by')
    readonly_fields = ('moment', 'created_by')  # Only applicable for the add transaction form (changing is not allowed)
    autocomplete_fields = ('source', 'target')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        """Sets the transaction creator and saves the transaction."""
        if not change:
            obj.created_by = request.user
        obj.save()
