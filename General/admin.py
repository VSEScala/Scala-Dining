from django.contrib import admin

from .models import PageVisitTracker, SiteUpdate


def mail_users(modeladmin, request, queryset):
    for site_update in queryset:
        site_update.mail_users()

    mail_users.short_description = "Mail the update to all users"


class SiteUpdateAdmin(admin.ModelAdmin):
    actions = [mail_users]


admin.site.register(SiteUpdate, SiteUpdateAdmin)
admin.site.register(PageVisitTracker)
