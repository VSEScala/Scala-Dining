from django.contrib import admin

from general.models import SiteUpdate, PageVisitTracker


class SiteUpdateAdmin(admin.ModelAdmin):
    pass


admin.site.register(SiteUpdate, SiteUpdateAdmin)
admin.site.register(PageVisitTracker)
