from django.contrib import admin

from dining.models import DiningEntryUser, DiningEntryExternal, DiningDayAnnouncement, \
    DiningComment, DiningWork, DiningList


@admin.register(DiningEntryUser, DiningEntryExternal)
class DiningEntryAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'dining_list', 'user')
    list_filter = ['dining_list__date', 'user']

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DiningList)
class DiningListAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'association', 'is_adjustable')
    list_filter = ['association', 'date']
    readonly_fields = ('date', 'diners', 'association')


@admin.register(DiningDayAnnouncement)
class DiningDayAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'slots_occupy')
    list_filter = ['date', 'slots_occupy']


admin.site.register(DiningComment)
admin.site.register(DiningWork)
