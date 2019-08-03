from django.views.generic import View, ListView, TemplateView
from django.shortcuts import render
from django.db.models import ObjectDoesNotExist
from django.utils import timezone
from datetime import datetime

from .models import SiteUpdate, PageVisitTracker
from UserDetails.models import Association


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


class UpgradeBalanceInstructionsView(View):
    template = "credit_management/balance_upgrade_instructions.html"
    context = {}
    change_date = timezone.make_aware(datetime(2019, 4, 14, 22, 20))

    def get(self, request):
        if request.user.is_authenticated:
            # Seperated for a possible prefilter to be implemented later (e.g. if active in kitchen)
            associations = Association.objects.order_by('slug')
            self.context['user_associations'] = associations.filter(usermembership__related_user=request.user)
            self.context['other_associations'] = associations.\
                exclude(id__in=self.context['user_associations'].values_list('id', flat=True))
        else:
            self.context['other_associations'] = Association.objects.all()

        return render(request, self.template, self.context)


class SuspensionInfoView(TemplateView):
    template_name = "general/suspended.html"