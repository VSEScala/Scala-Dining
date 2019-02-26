from django.views.generic import View
from django.shortcuts import render
from .models import SiteUpdate, PageVisitTracker
from django.utils import timezone
import math


class PageListView:
    """
    A base class used for views that prevent some sort of navigatable list with multiple pages
    """
    context = {}
    length = 10

    def set_up_list(self, entries, page):
        lower_bound = self.length * (page - 1)
        upper_bound = self.length * page

        self.context['entries'] = entries[lower_bound:upper_bound]
        self.context['page'] = page
        self.context['pages'] = math.ceil(len(entries) / self.length)
        if self.context['pages'] > 1:
            self.context['show_page_navigation'] = True
            self.context['pages'] = range(1, self.context['pages']+1)
        else:
            self.context['show_page_navigation'] = False


class SiteUpdateView(View, PageListView):
    template = "general/version_overview.html"
    length = 4

    def get(self, request, page=1):

        # Set up the list display
        updates = SiteUpdate.objects.order_by('-date').all()
        super(SiteUpdateView, self).set_up_list(updates, page)
        if updates:
            latest_update = updates[0].date
        else:
            latest_update = timezone.now()

        self.context['latest_visit'] = PageVisitTracker.get_latest_vistit('updates', request.user, update=True)
        self.context['latest_update'] = latest_update

        return render(request, self.template, self.context)


class BugReportView(View):
    template = "general/bugreport.html"
    context = {}

    def get(self, request):
        self.context["Sourcepage"] = request.GET.get('source', '')
        return render(request, self.template, self.context)


class RulesPageView(View):
    template = "general/rules_and_regulations.html"
    context = {}

    def get(self, request):
        return render(request, self.template, self.context)