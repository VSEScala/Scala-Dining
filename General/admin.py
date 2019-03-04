from UserDetails.admin import site
from .models import SiteUpdate, PageVisitTracker

site.register(SiteUpdate)
site.register(PageVisitTracker)
