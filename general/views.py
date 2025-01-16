from datetime import datetime
from os import getenv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ObjectDoesNotExist
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render
from django.template.loader import TemplateDoesNotExist, get_template
from django.utils.timezone import make_aware, now
from django.views.generic import ListView, TemplateView, View

from general.models import PageVisitTracker, SiteUpdate
from userdetails.models import Association


class SiteUpdateView(LoginRequiredMixin, ListView):
    # DEPRECATED: This view is currently not in use.

    template_name = "general/site_updates.html"
    paginate_by = 4

    def get_queryset(self):
        return SiteUpdate.objects.order_by("-date").all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            latest_update = SiteUpdate.objects.latest("date").date
        except ObjectDoesNotExist:
            latest_update = now()

        context["latest_visit"] = PageVisitTracker.get_latest_visit(
            "updates", self.request.user, update=True
        )
        context["latest_update"] = latest_update

        return context

    @staticmethod
    def has_new_update(user):
        """Checks whether a new update for the given user is present."""
        # Disabled to reduces queries on page load
        return False
        # visit_timestamp = PageVisitTracker.get_latest_visit("updates", user)
        # if visit_timestamp is None:
        #     return False
        # return SiteUpdate.objects.latest("date").date > visit_timestamp


class HelpPageView(TemplateView):
    template_name = "general/help_layout.html"

    def get_context_data(self, **kwargs):
        """Loads app build date from file."""
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "commit_sha": getenv("COMMIT_SHA"),
            }
        )
        return context


class RulesPageView(View):
    template = "general/rules_and_regulations.html"
    context = {}
    change_date = make_aware(datetime(2019, 4, 14, 22, 20))

    def get(self, request):
        # Store the recent updates/visit data in the local context
        if request.user.is_authenticated:
            self.context["latest_visit"] = PageVisitTracker.get_latest_visit(
                "rules", request.user, update=True
            )
        self.context["latest_update"] = self.change_date

        return render(request, self.template, self.context)

    @staticmethod
    def has_new_update(user):
        """Checks whether a new update for the given user is present."""
        # Disabled to reduce queries on page load
        return False
        # visit_timestamp = PageVisitTracker.get_latest_visit("rules", user)
        # if visit_timestamp is None:
        #     return False
        #
        # return RulesPageView.change_date > visit_timestamp


class UpgradeBalanceInstructionsView(TemplateView):
    template_name = "credit_management/balance_upgrade_instructions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            associations = Association.objects.order_by("short_name")
            context["user_associations"] = associations.filter(
                usermembership__related_user=self.request.user
            ).exclude(
                # User wasn't verified and isn't pending (verification date is empty for pending users)
                usermembership__is_verified=False,
                usermembership__verified_on__isnull=False,
            )
            context["other_associations"] = associations.exclude(
                id__in=context["user_associations"].values_list("id", flat=True)
            )
        else:
            context["other_associations"] = Association.objects.all()

        return context


class EmailTemplateView(View):
    """A view to test mail templates with.

    The ContentFactory class inside ensures that when an object does not reside in the context,
    it prints the query name instead.
    """

    class ContentFactory(dict):
        """A dictionary that either returns the content, or a new dictionary with the name of the searched content.

        Used to replace un-found content in the template with the original name.
        """

        # Note: subclassing dict is a very invasive solution for a problem that
        #  can be solved with a much simpler less invasive solution. Please do
        #  not use a dict subclass for this problem.

        def __init__(self, name="", dictionary: dict = None):
            self._dict = dictionary or {}
            self._name = name

        def __getattr__(self, key):
            return self[key]

        def __getitem__(self, key):
            item = self._dict.get(key, None)
            if item is None:
                return EmailTemplateView.create_new_factory(
                    name="{name}.{key}".format(name=self._name, key=key)
                )
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

        template_location = request.GET.get("template", None) + ".html"

        try:
            get_template(template_location)
        except TemplateDoesNotExist:
            return Http404("Given template name not found")

        context = self.ContentFactory(dictionary=request.GET.dict())
        context["request"] = request
        context["user"] = request.user
        return render(None, template_location, context)
