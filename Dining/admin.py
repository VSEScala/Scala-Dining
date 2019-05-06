from django.contrib import admin

from Dining.models import *


class DiningSettingAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    fields = ('user', 'allergies',)
    readonly_fields = ('user',)

    actions = ['credit_zero']

    list_display = ('user', 'allergies')
    list_filter = ['user__usermembership__association']


class DiningEntryAdmin(admin.ModelAdmin):
    """
    Sets up the admin for the dining list entries
    """

    list_display = ('__str__', 'dining_list', 'user')
    list_filter = ['dining_list__date', 'user']


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
              ('kitchen_cost', 'dining_cost', 'auto_pay'),
              'payment_link')


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


admin.site.register(UserDiningSettings, DiningSettingAdmin)
admin.site.register(DiningList, DiningListAdmin)
#admin.site.register(DiningListComment, DiningListCommentsAdmin)
admin.site.register(DiningDayAnnouncement)
admin.site.register(DiningComment)
admin.site.register(DiningEntryUser, DiningEntryAdmin)
admin.site.register(DiningEntryExternal, DiningEntryAdmin)
admin.site.register(DiningWork)
