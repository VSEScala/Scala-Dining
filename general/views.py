from datetime import datetime
from os import getenv

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import mail
from django.utils import timezone
from django.views.generic import TemplateView

from general.forms import DateRangeForm
from userdetails.models import Association


class DateRangeFilterMixin:
    """A mixin that retrieves a date range from GET query params."""

    date_start = None
    date_end = None
    date_range_form = None

    def dispatch(self, request, *args, **kwargs):
        if 'date_start' in request.GET and 'date_end' in request.GET:
            self.date_range_form = DateRangeForm(request.GET)
        else:
            self.date_range_form = DateRangeForm()

        if self.date_range_form.is_valid():
            self.date_start = self.date_range_form.cleaned_data['date_start']
            self.date_end = self.date_range_form.cleaned_data['date_end']

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date_range_form'] = self.date_range_form
        return context


class HelpPageView(TemplateView):
    template_name = "general/help_layout.html"

    def get_context_data(self, **kwargs):
        """Loads app build info from environment."""
        context = super().get_context_data(**kwargs)

        build_date = getenv('BUILD_TIMESTAMP')
        if build_date:
            build_date = datetime.fromtimestamp(float(build_date), timezone.utc)
        context.update({
            'build_date': build_date,
            'commit_sha': getenv('COMMIT_SHA'),
        })
        return context


class RulesPageView(TemplateView):
    template_name = "general/rules_and_regulations.html"


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


class OutboxView(LoginRequiredMixin, TemplateView):
    """This view returns the mail messages that have been sent and kept in memory."""
    template_name = 'general/outbox.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            outbox = mail.outbox
        except AttributeError:
            outbox = []

        context.update({
            'outbox': outbox,
            # True if the backend is configured correctly
            'configured': settings.EMAIL_BACKEND == 'django.core.mail.backends.locmem.EmailBackend',
        })
        return context
