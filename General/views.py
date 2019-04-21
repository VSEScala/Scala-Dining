from django.views.generic import View, ListView
from django.shortcuts import render
from django.db.models import ObjectDoesNotExist
from .models import SiteUpdate, PageVisitTracker
from django.utils import timezone
from datetime import datetime


class SiteUpdateView(ListView):
    template_name = "general/site_updates.html"
    paginate_by = 4

    def get_queryset(self):
        return SiteUpdate.objects.order_by('-date').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            latest_update = SiteUpdate.objects.latest('date').date
        except ObjectDoesNotExist:
            latest_update = timezone.now()

        context['latest_visit'] = PageVisitTracker.get_latest_visit('updates', self.request.user, update=True)
        context['latest_update'] = latest_update

        return context

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


class HelpPageView(View):
    template = "general/help_layout.html"
    context = {}

    def get(self, request):
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
