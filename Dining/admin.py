from django.contrib import admin
from Dining.models import UserDiningSettings, DiningList, DiningEntry, DiningEntryExternal, DiningComments, UserDiningStats


# Register your models here.



class DiningSettingsAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('user', 'canSubscribeDiningList')

    fields = ('user',
              ('canSubscribeDiningList', 'canClaimDiningList'),
              'allergies',)
              #('count_subscribed', 'count_shopped', 'count_cooked', 'count_cleaned'),)

    actions = ['credit_zero']

    def credit_zero(self, request, queryset):
        queryset.update(count_subscribed=0, count_shopped=0, count_cooked=0, count_cleaned=0)
    credit_zero.short_description = "Set credit to zero"

    #readonly_fields = ('user',)


class DiningListEntryLink(admin.StackedInline):
    """
    Create the entries in the dininglist (taken from a new table)
    """
    model = DiningEntry
    fields = (('user', 'has_shopped', 'has_cooked', 'has_cleaned', 'has_paid'),)
    verbose_name = ""
    verbose_name_plural = "Dining Entries"
    extra = 1

class DiningListExternalEntryLink(admin.StackedInline):
    """
    Create the external entries in the dininglist (taken from a new table)
    """
    model = DiningEntryExternal
    verbose_name_plural = "External entries"
    fields = (('name', 'user', 'has_paid'),)
    extra = 0


class DiningListAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('__str__', 'association', 'diners', 'isAdjustable')
    list_filter = ['association', 'date']

    #readonly_fields = ('date', 'diners', 'dinner_cost_single')
    inlines = [DiningListEntryLink, DiningListExternalEntryLink]
    fields = (('date', 'sign_up_deadline', 'days_adjustable'),
              ('dish', 'name'),
              ('claimed_by', 'association', 'purchaser', 'limit_signups_to_association_only'),
              ('min_diners', 'max_diners', 'diners'),
              ('kitchen_cost', 'dinner_cost_single'),
              ('dinner_cost_total', 'auto_pay', 'dinner_cost_keep_single_constant'),)


class DininglistCommentsLink(admin.StackedInline):
    """
    Create the additional information on the user page (taken from a new table)
    """
    model = DiningComments
    fields = (('poster', 'timestamp'), 'message',)
    verbose_name = ""
    verbose_name_plural = "Comments"
    readonly_fields = ('timestamp',)
    extra = 0


class DiningListComment(DiningList):
    """
    Create a meta class to obtain personal names instead of usernames
    """
    class Meta:
        proxy = True


class DiningListCommentsAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('__str__', 'association', 'diners')
    list_filter = ['association', 'date']

    readonly_fields = ('date', 'claimed_by', 'association', 'diners')
    inlines = [DininglistCommentsLink]
    fields = ('date', ('claimed_by', 'association', 'diners'),)


admin.site.register(UserDiningSettings, DiningSettingsAdmin)
admin.site.register(DiningList, DiningListAdmin)
admin.site.register(DiningListComment, DiningListCommentsAdmin)
admin.site.register(UserDiningStats)
