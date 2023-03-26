from django.contrib import admin

from dining.models import DiningDayAnnouncement, DiningComment, DiningList, DiningEntry, DeletedList


@admin.register(DiningEntry)
class DiningEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'dining_list', 'user', 'external_name', 'has_shopped', 'has_cooked', 'has_cleaned')
    list_filter = ('dining_list__date',)
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'user__email')

    # We do not allow adding/deleting/changing dining entries because money is involved.

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DiningList)
class DiningListAdmin(admin.ModelAdmin):
    list_display = ('date', 'association', 'dish', 'is_adjustable')
    list_filter = ('association', 'date')
    readonly_fields = ('date', 'diners', 'association')
    filter_horizontal = ('owners',)


@admin.register(DiningDayAnnouncement)
class DiningDayAnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'slots_occupy')
    list_filter = ('date', 'slots_occupy')


admin.site.register(DiningComment)


@admin.register(DeletedList)
class DeletedListAdmin(admin.ModelAdmin):
    # list_display = ('date', 'deleted_by')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
