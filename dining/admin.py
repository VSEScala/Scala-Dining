from django.contrib import admin

from dining.models import (
    DeletedList,
    DiningComment,
    DiningDayAnnouncement,
    DiningEntry,
    DiningList,
)


@admin.register(DiningEntry)
class DiningEntryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "dining_list",
        "user",
        "external_name",
        "has_shopped",
        "has_cooked",
        "has_cleaned",
    )
    list_filter = ("dining_list__date",)
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__username",
        "user__email",
    )

    # We do not allow adding/deleting/changing dining entries because money is involved.

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(DiningList)
class DiningListAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "association",
        "dish",
        "is_adjustable",
        "limit_signups_to_association_only",
    )
    list_filter = ("association", "date", "limit_signups_to_association_only")
    readonly_fields = ("diners",)
    filter_horizontal = ("owners",)


@admin.register(DiningDayAnnouncement)
class DiningDayAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "slots_occupy")
    list_filter = ("date", "slots_occupy")
    ordering = ("-date",)


@admin.register(DiningComment)
class DiningCommentAdmin(admin.ModelAdmin):
    list_display = ("dining_list", "timestamp", "poster", "message", "deleted")
    search_fields = ("message",)
    readonly_fields = ("dining_list", "timestamp", "poster", "email_sent")
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False


@admin.register(DeletedList)
class DeletedListAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
