from django.contrib import admin

from .models import SiteUpdate, PageVisitTracker

admin.site.register(SiteUpdate)
admin.site.register(PageVisitTracker)
