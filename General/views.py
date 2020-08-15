from django.views.generic import View, ListView, TemplateView
from django.http import HttpResponseForbidden, Http404, HttpResponse
from django.shortcuts import render
from django.db.models import ObjectDoesNotExist
from django.template.loader import get_template, TemplateDoesNotExist
from django.utils import timezone
from datetime import datetime, timedelta

from .models import SiteUpdate, PageVisitTracker
from General.forms import DateRangeForm
from UserDetails.models import Association


class DateRangeFilterMixin:
    """
    A filter that takes time of day attributes from the GET attributes
    """
    date_start = None
    date_end = None
    default_time_length = timedelta(days=3650)
    date_range_form = None

    def dispatch(self, request, *args, **kwargs):
        if request.GET:
            self.date_range_form = DateRangeForm(request.GET)
        else:
            self.date_range_form = DateRangeForm()

        if self.date_range_form.is_valid():
            self.date_start = self.date_range_form.cleaned_data['date_start']
            self.date_end = self.date_range_form.cleaned_data['date_end']

        return super(DateRangeFilterMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(DateRangeFilterMixin, self).get_context_data(**kwargs)
        context['date_range_form'] = self.date_range_form

        return context


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


class UpgradeBalanceInstructionsView(TemplateView):
    template_name = "credit_management/balance_upgrade_instructions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Separated for a possible prefilter to be implemented later (e.g. if active in kitchen)
            associations = Association.objects.order_by('slug')
            context['user_associations'] = associations.filter(usermembership__related_user=self.request.user)
            context['other_associations'] = associations. \
                exclude(id__in=context['user_associations'].values_list('id', flat=True))
        else:
            context['other_associations'] = Association.objects.all()

        return context


class EmailTemplateView(View):
    """
    A view to test mail templates with.
    The contentfactory class inside ensures that when an object does not reside in the context,
    it prints the query name instead
    """

    class ContentFactory(dict):
        """
        A dictionary that either returns the content, or a new dictionary with the name of the searched content
        Used to replace unfound content in the template with the original name
        """
        def __init__(self, name="", dictionary={}):
            self._dict = dictionary
            self._name = name

        def __getattr__(self, key):
            return self[key]

        def __getitem__(self, key):
            item = self._dict.get(key, None)
            if item is None:
                return EmailTemplateView.create_new_factory(name="{name}.{key}".format(name=self._name, key=key))
            else:
                return item

        def __contains__(self, item):
            # All objects exist, either in the dictionary, or a new one is created
            return True

        def __str__(self):
            return "-{}-".format(self._name)

        def __repr__(self):
            return self._dict.__str__()

        def __setitem__(self, key, value):
            self._dict[key] = value

    @staticmethod
    def create_new_factory(name=""):
        return EmailTemplateView.ContentFactory(name=name)

    def get(self, request):
        if not request.user.is_superuser:
            return HttpResponseForbidden("You do not have permission to view this")

        template_location = request.GET.get('template', None) + ".html"

        try:
            template = get_template(template_location, using='EmailTemplates')
        except TemplateDoesNotExist:
            return Http404("Given template name not found")

        context = self.ContentFactory(dictionary=request.GET.dict())
        context['request'] = request
        context['user'] = request.user
        return render(None, template_location, context, using='EmailTemplates')


