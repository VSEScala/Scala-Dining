from django.contrib import admin

from general.models import SiteUpdate


class SiteUpdateAdmin(admin.ModelAdmin):
    pass


admin.site.register(SiteUpdate, SiteUpdateAdmin)
