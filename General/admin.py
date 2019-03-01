from django.contrib import admin
from .models import SiteUpdate, PageVisitTracker

# Register your models here.

admin.site.register(SiteUpdate)
admin.site.register(PageVisitTracker)
