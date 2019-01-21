from django.contrib import admin
from Dining.models import *


class DiningSettingsAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('user', )

    fields = ('user', 'allergies',)

    actions = ['credit_zero']

    #readonly_fields = ('user',)


class DiningListEntryLink(admin.StackedInline):
    """
    Create the entries in the dininglist (taken from a new table)
    """
    model = DiningEntryUser
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

    list_display = ('__str__', 'association', 'is_adjustable')
    list_filter = ['association', 'date']

    #readonly_fields = ('date', 'diners', 'dinner_cost_single')
    inlines = [DiningListEntryLink, DiningListExternalEntryLink]
    fields = (('date', 'sign_up_deadline', 'adjustable_duration'),
              ('dish'),
              ('claimed_by', 'association', 'purchaser', 'limit_signups_to_association_only'),
              ('min_diners', 'max_diners'),
              ('kitchen_cost', 'dinner_cost_single'),
              ('dinner_cost_total', 'auto_pay', 'dinner_cost_keep_single_constant'),)


class DininglistCommentsLink(admin.StackedInline):
    """
    Create the additional information on the user page (taken from a new table)
    """
    model = DiningComment
    fields = (('poster', 'timestamp'), 'message', 'pinned_to_top')
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

    list_display = ('__str__', 'association')
    list_filter = ['association', 'date']

    readonly_fields = ('date', 'claimed_by', 'association')
    inlines = [DininglistCommentsLink]
    fields = ('date', ('claimed_by', 'association'),)


#admin.site.register(UserDiningSettings, DiningSettingsAdmin)
admin.site.register(DiningList, DiningListAdmin)
#admin.site.register(DiningListComment, DiningListCommentsAdmin)
#admin.site.register(DiningDayAnnouncements)
#admin.site.register(DiningCommentView)
admin.site.register(DiningEntry)
admin.site.register(DiningEntryUser)
admin.site.register(DiningEntryExternal)
admin.site.register(DiningWork)
