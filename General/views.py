from django.views.generic import View
from django.shortcuts import render
from .models import SiteUpdate, PageVisitTracker
from django.utils import timezone
from datetime import datetime
import math


class PageListMixin:
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


class SiteUpdateView(View, PageListMixin):
    template = "general/version_overview.html"

    def get(self, request, page=1):

        # Set up the list display
        updates = SiteUpdate.objects.order_by('-date').all()
        super(SiteUpdateView, self).set_up_list(updates, page)
        if updates:
            latest_update = updates[0].date
        else:
            latest_update = timezone.now()

        self.context['latest_visit'] = PageVisitTracker.get_latest_visit('updates', request.user, update=True)
        self.context['latest_update'] = latest_update

        return render(request, self.template, self.context)


    @staticmethod
    def has_new_update(user):
        """
        Checks whether a new update for the given user is present
        :param user:
        :return:
        """
        visit_timestamp = PageVisitTracker.get_latest_visit('updates', user)
        if visit_timestamp is None:
            return False
        return SiteUpdate.objects.latest('date').date > visit_timestamp


class BugReportView(View):
    template = "general/bugreport.html"
    context = {}

    def get(self, request):
        self.context["Sourcepage"] = request.GET.get('source', '')
        return render(request, self.template, self.context)


class RulesPageView(View):
    template = "general/rules_and_regulations.html"
    context = {}
    change_date = timezone.make_aware(datetime(2019, 4, 14, 22, 20))

    def get(self, request):
        # Store the recent updates/visit data in the local context
        if request.user.is_authenticated:
            self.context['latest_visit'] = PageVisitTracker.get_latest_visit('rules', request.user, update=True)
        self.context['latest_update'] = self.change_date

        return render(request, self.template, self.context)

    @staticmethod
    def has_new_update(user):
        """
        Checks whether a new update for the given user is present
        :param user:
        :return:
        """
        visit_timestamp = PageVisitTracker.get_latest_visit('rules', user)
        if visit_timestamp is None:
            return False

        return RulesPageView.change_date > visit_timestamp
