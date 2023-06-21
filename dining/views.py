import csv
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, TemplateView, View
from django.views.generic.detail import SingleObjectMixin

from dining.datesequence import sequenced_date
from dining.forms import (
    CreateSlotForm,
    DiningCommentForm,
    DiningEntryDeleteForm,
    DiningEntryExternalForm,
    DiningEntryInternalForm,
    DiningInfoForm,
    DiningListDeleteForm,
    DiningPaymentForm,
    SendReminderForm,
)
from dining.models import (
    DiningComment,
    DiningCommentVisitTracker,
    DiningDayAnnouncement,
    DiningEntry,
    DiningList,
)
from general.mail_control import send_templated_mail
from userdetails.models import Association, User


def index(request):
    d = sequenced_date.upcoming()
    return redirect("day_view", year=d.year, month=d.month, day=d.day)


class DayMixin:
    """Adds useful thingies to context and self that have to do with the request date."""

    date = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "date": self.date,
                "date_diff": (
                    self.date - date.today()
                ).days,  # Nr. of days between date and today
            }
        )
        return context

    def init_date(self):
        """Fetches the date from the request arguments."""
        if self.date:
            # Already initialized
            return
        try:
            self.date = sequenced_date.fromdate(
                date(self.kwargs["year"], self.kwargs["month"], self.kwargs["day"])
            )
        except ValueError:
            raise Http404("Invalid date")

    def dispatch(self, request, *args, **kwargs):
        """Initializes date before get/post is called."""
        self.init_date()
        return super().dispatch(request, *args, **kwargs)

    def reverse(self, *args, kwargs=None, **other_kwargs):
        """URL reverse which expands the date."""
        kwargs = kwargs or {}
        kwargs["year"] = self.date.year
        kwargs["month"] = self.date.month
        kwargs["day"] = self.date.day
        return reverse(*args, kwargs=kwargs, **other_kwargs)


class DayView(LoginRequiredMixin, DayMixin, TemplateView):
    """Shows the dining lists on a given date.

    Task:
    -   display all occupied dining slots
    -   allow for additional dining slots to be made if place is available
    """

    template_name = "dining_lists/dining_day.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["dining_lists"] = DiningList.objects.filter(date=self.date)
        context["Announcements"] = DiningDayAnnouncement.objects.filter(date=self.date)

        # Make the view clickable
        context["interactive"] = True

        return context


class DailyDinersCSVView(LoginRequiredMixin, View):
    """Returns a CSV file with all diners of that day."""

    def get(self, request, *args, **kwargs):
        # Only superusers can access this page
        if not request.user.is_superuser:
            return HttpResponseForbidden

        # Get the end date
        date_end = request.GET.get("to", None)
        if date_end:
            # Why do you use datetime here and not date?
            date_end = datetime.strptime(date_end, "%d/%m/%y")
        else:
            date_end = timezone.now()

        # Filter on a start date
        date_start = request.GET.get("from", None)
        if date_start:
            date_start = datetime.strptime(date_start, "%d/%m/%y")
        else:
            date_start = date_end

        # Count all dining entries in the given period
        entry_count = Count(
            "diningentry",
            filter=(
                Q(diningentry__dining_list__date__lte=date_end)
                & Q(diningentry__dining_list__date__gte=date_start)
            ),
        )

        # Annotate the counts to the user
        users = User.objects.annotate(diningentry_count=entry_count)
        users = users.filter(diningentry_count__gt=0)

        # Get the related membership objects for speed optimisation
        users.select_related("usermembership")

        # Get all associations
        associations = Association.objects.all()

        # Create the CSV file
        # Set up
        response = HttpResponse(content_type="text/csv")
        response[
            "Content-Disposition"
        ] = 'attachment; filename="association_members.csv"'
        csv_writer = csv.writer(response)

        # Write header
        header = ["Name", "Joined"]
        for association in associations:
            header += [association.name]

        csv_writer.writerow(header)

        # Write content
        for user in users:
            user_info = [user.get_full_name(), user.diningentry_count]

            # Get all associated memberships
            memberships = []
            for association in associations:
                if user.is_verified_member_of(association):
                    memberships.append(1)
                else:
                    memberships.append(0)

            csv_writer.writerow(user_info + memberships)

        # Return the CSV file
        return response


class NewSlotView(LoginRequiredMixin, DayMixin, TemplateView):
    """Creation page for a new dining list."""

    template_name = "dining_lists/dining_add.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context.update(
            {
                "slot_form": CreateSlotForm(
                    self.request.user, instance=DiningList(date=self.date)
                )
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()

        context["slot_form"] = CreateSlotForm(
            request.user, request.POST, instance=DiningList(date=self.date)
        )

        if context["slot_form"].is_valid():
            dining_list = context["slot_form"].save()
            messages.success(request, "You successfully created a new dining list")
            return redirect(dining_list)

        return self.render_to_response(context)


class DiningListMixin(DayMixin):
    """Mixin for a dining list detail page."""

    dining_list = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "dining_list": self.dining_list,
            }
        )
        return context

    def init_dining_list(self):
        """Fetches the dining list using the request arguments."""
        if self.dining_list:
            # Already initialized
            return
        # Needs initialized date
        self.init_date()
        self.dining_list = get_object_or_404(
            DiningList, date=self.date, association__slug=self.kwargs["identifier"]
        )

    def dispatch(self, request, *args, **kwargs):
        self.init_dining_list()
        return super().dispatch(request, *args, **kwargs)

    def reverse(self, *args, kwargs=None, **other_kwargs):
        kwargs = kwargs or {}
        kwargs["identifier"] = self.dining_list.association.slug
        return super().reverse(*args, kwargs=kwargs, **other_kwargs)


class UpdateSlotViewTrackerMixin:
    """Sets comments_total and comments_unread context variables."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get the amount of messages
        context["comments_total"] = self.dining_list.diningcomment_set.count()
        # Get the amount of unread messages
        view_time = DiningCommentVisitTracker.get_latest_visit(
            user=self.request.user, dining_list=self.dining_list
        )
        if view_time is None:
            context["comments_unread"] = context["comments_total"]
        else:
            context["comments_unread"] = self.dining_list.diningcomment_set.filter(
                timestamp__gte=view_time
            ).count()

        return context


# We use 2 different terminologies for the same thing, 'slot' and 'dining list'. We should get rid of 'slot'.


class SlotMixin(LoginRequiredMixin, DiningListMixin, UpdateSlotViewTrackerMixin):
    """Mixin for a dining list detail page."""

    pass


class EntryAddView(LoginRequiredMixin, DiningListMixin, TemplateView):
    template_name = "dining_lists/dining_entry_add.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "user_form": DiningEntryInternalForm(),
                "external_form": DiningEntryExternalForm(),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        # This post method always redirects, does not show the form again on validation errors, so that we don't have
        #  to write HTML for displaying these errors (they are already in a Django message).

        # Do form shenanigans
        if "add_external" in request.POST:
            entry = DiningEntry(
                user=request.user, dining_list=self.dining_list, created_by=request.user
            )
            form = DiningEntryExternalForm(request.POST, instance=entry)
        else:
            entry = DiningEntry(dining_list=self.dining_list, created_by=request.user)
            form = DiningEntryInternalForm(request.POST, instance=entry)

        if form.is_valid():
            entry = form.save()

            # The entry is for another existing user, send a mail to them.
            if entry.is_internal() and entry.user != request.user:
                send_templated_mail(
                    "mail/dining_entry_added_by",
                    entry.user,
                    context={"entry": entry, "dining_list": entry.dining_list},
                    request=request,
                )
                messages.success(
                    request,
                    "You successfully added {} to the dining list".format(
                        entry.user.get_short_name()
                    ),
                )

            # The entry is for an external diner, provide a message.
            if entry.is_external():
                messages.success(
                    request,
                    "You successfully added {} to the dining list".format(
                        entry.external_name
                    ),
                )
        else:
            # The form was invalid, put the errors in a message.
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(
                        request,
                        "{}: {}".format(field, error)
                        if field != NON_FIELD_ERRORS
                        else error,
                    )

        # Always redirect to the dining list page
        return redirect(self.dining_list)


class EntryDeleteView(LoginRequiredMixin, SingleObjectMixin, View):
    model = DiningEntry

    def post(self, request, *args, **kwargs):
        entry = self.get_object()

        # Process deletion
        form = DiningEntryDeleteForm(entry, request.user, {})
        if form.is_valid():
            form.execute()

            # Success message
            if entry.is_internal() and entry.user == request.user:
                success_msg = "You are removed from the dining list"
            elif entry.is_external():
                success_msg = "The external diner is removed from the dining list"
            else:
                success_msg = "The user is removed from the dining list"
            messages.success(request, success_msg)

            # Send a mail when someone else does the removal
            if entry.user != request.user:
                context = {
                    "entry": entry,
                    "dining_list": entry.dining_list,
                    "remover": request.user,
                }
                if entry.is_external():
                    send_templated_mail(
                        "mail/dining_entry_external_removed_by",
                        entry.user,
                        context,
                        request,
                    )
                else:
                    send_templated_mail(
                        "mail/dining_entry_removed_by", entry.user, context, request
                    )

        else:
            for error in form.non_field_errors():
                messages.error(request, error)

        # Go to next
        next_url = request.GET.get("next")
        if url_has_allowed_host_and_scheme(next_url, request.get_host()):
            return HttpResponseRedirect(next_url)
        else:
            return HttpResponseRedirect(entry.dining_list.get_absolute_url())


class SlotListView(SlotMixin, TemplateView):
    template_name = "dining_lists/dining_slot_diners.html"

    def can_edit_stats(self):
        """Returns whether the current user can edit work and paid stats.

        The user must be owner. It is possible to edit the stats after the
        dining list is no longer adjustable.
        """
        return self.dining_list.is_owner(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "entries": self.dining_list.dining_entries.order_by(
                    "user__first_name", "user__last_name", "external_name"
                ),
                "can_edit_stats": self.can_edit_stats(),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        if not self.can_edit_stats():
            raise PermissionDenied

        # The code above checks that the user is allowed to edit this dining
        # list. It does not check whether the given dining entry ID is actually
        # part of the dining list. To check that, we provide the dining list to
        # get_object_or_404(). If we did not do that, the user could change all
        # dining entries across all lists.

        entry = get_object_or_404(
            DiningEntry, id=request.POST.get("entry_id"), dining_list=self.dining_list
        )

        # We toggle the given stat value, based on the previous value as was submitted by the form.
        stat = request.POST.get("toggle")
        if stat == "shopped":
            entry.has_shopped = not bool(request.POST.get("shopped_val"))
        elif stat == "cooked":
            entry.has_cooked = not bool(request.POST.get("cooked_val"))
        elif stat == "cleaned":
            entry.has_cleaned = not bool(request.POST.get("cleaned_val"))
        elif stat == "paid":
            entry.has_paid = not bool(request.POST.get("paid_val"))

        entry.save()
        return HttpResponseRedirect(self.reverse("slot_list"))


class SlotInfoView(
    LoginRequiredMixin, DiningListMixin, UpdateSlotViewTrackerMixin, FormView
):
    template_name = "dining_lists/dining_slot_info.html"
    form_class = DiningCommentForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "instance": DiningComment(
                    dining_list=self.dining_list, poster=self.request.user
                ),
            }
        )
        return kwargs

    def get_success_url(self):
        return self.reverse("slot_details")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "comments": self.dining_list.diningcomment_set.order_by(
                    "-pinned_to_top", "timestamp"
                ).all(),
                "last_visited": DiningCommentVisitTracker.get_latest_visit(
                    user=self.request.user, dining_list=self.dining_list, update=True
                ),
                "number_of_allergies": self.dining_list.internal_dining_entries()
                .exclude(user__allergies="")
                .count(),
            }
        )
        return context

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class SlotAllergyView(SlotMixin, TemplateView):
    template_name = "dining_lists/dining_slot_allergy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entries = self.dining_list.internal_dining_entries().exclude(user__allergies="")
        context.update(
            {"allergy_entries": entries.order_by("user__first_name", "user__last_name")}
        )
        return context


class SlotOwnerMixin:
    """Slot mixin extension that makes it only accessible for dining list owners."""

    def dispatch(self, request, *args, **kwargs):
        # Initialise dining list
        self.init_dining_list()
        # Check permission
        if not self.dining_list.is_owner(request.user):
            raise PermissionDenied
        # Dispatch
        return super().dispatch(request, *args, **kwargs)


# Could possibly use the Django built-in FormView or ModelFormView in combination with FormSet
class SlotInfoChangeView(SlotMixin, SlotOwnerMixin, TemplateView):
    template_name = "dining_lists/dining_slot_info_alter.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update(
            {
                "info_form": DiningInfoForm(instance=self.dining_list, prefix="info"),
                "payment_form": DiningPaymentForm(
                    instance=self.dining_list, prefix="payment"
                ),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        """
        ## Story time
        This suffered from the most awesome bug. Earlier, one form would be saved if it was valid, even when the other
        form wasn't valid. E.g. when the info form was not valid while the payment form is actually valid, the payment
        form would get saved. However the payment form uses the same dining list instance as for the info form, and
        invalid field values of the info form do get applied to the dining list instance, they are just normally not
        saved in the database because the form would be invalid. However the payment form is valid and therefore saves
        the dining list anyway, with the invalid field values.

        An explicit include of only fields that were part of the form during saving prevented the bug from manifesting
        (perhaps it was meant that way?).
        """

        info_form = DiningInfoForm(
            request.POST, instance=self.dining_list, prefix="info"
        )
        payment_form = DiningPaymentForm(
            request.POST, instance=self.dining_list, prefix="payment"
        )

        # Save and redirect if forms are valid, stay otherwise
        if info_form.is_valid() and payment_form.is_valid():
            info_form.save()
            payment_form.save()
            messages.success(request, "Changes successfully saved")

            return HttpResponseRedirect(self.reverse("slot_details"))

        context.update(
            {
                "info_form": info_form,
                "payment_form": payment_form,
            }
        )

        return self.render_to_response(context)


class SlotDeleteView(SlotMixin, SlotOwnerMixin, FormView):
    """Page for slot deletion.

    Page is only available for slot owners.
    """

    template_name = "dining_lists/dining_slot_delete.html"
    form_class = DiningListDeleteForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(
            {
                "instance": self.dining_list,
            }
        )
        return kwargs

    def get_day_view_url(self):
        return super(DiningListMixin, self).reverse("day_view")

    def get_success_url(self):
        return self.get_day_view_url()

    def form_valid(self, form):
        with transaction.atomic():
            form.execute_and_notify(self.request, self.get_day_view_url())
            messages.success(self.request, "Dining list is deleted")
        return super().form_valid(form)


class SlotPaymentView(SlotMixin, SlotOwnerMixin, FormView):
    """A view class that allows dining list owners to send payment reminders."""

    form_class = SendReminderForm

    def get(self, request, *args, **kwargs):
        # This is to prevent TemplateView.get to fail because template_name is not defined.
        return self.http_method_not_allowed(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["dining_list"] = self.dining_list
        return kwargs

    def get_success_url(self):
        return self.reverse("slot_details")

    def form_invalid(self, form):
        for e in form.non_field_errors():
            messages.info(self.request, str(e))
        return HttpResponseRedirect(self.get_success_url())

    def form_valid(self, form):
        success = form.send_reminder(self.request)
        if not success:
            messages.success(
                self.request,
                "Diners have been informed recently, you can send a new mail momentarily",
            )
        else:
            messages.success(self.request, "Diners have been informed")
        return super().form_valid(form)


class StatisticsView(LoginRequiredMixin, TemplateView):
    template_name = "dining_lists/statistics.html"

    def get_range(self):
        """Returns the user-defined date range or a default range."""
        today = timezone.now().date()
        # Default boundary is August 1st. We could also do September 1st but then we
        # might miss some early year dining lists.
        range_from = date(today.year - 1 if today.month < 8 else today.year, 8, 1)
        range_to = range_from.replace(year=range_from.year + 1)
        try:
            range_from = date.fromisoformat(self.request.GET.get("from") or "")
        except ValueError:
            pass
        try:
            range_to = date.fromisoformat(self.request.GET.get("to") or "")
        except ValueError:
            pass
        return range_from, range_to

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        range_from, range_to = self.get_range()

        # Dining lists in the period
        lists = DiningList.objects.filter(date__gte=range_from, date__lt=range_to)
        # Users who dined in the given period (excludes external entries)
        users = User.objects.filter(
            diningentry__dining_list__in=lists, diningentry__external_name=""
        ).distinct()
        # Entries in given period
        entries = DiningEntry.objects.filter(dining_list__in=lists)
        # Filter on association
        per_association = {
            a: {
                "users": users.filter(
                    usermembership__association=a, usermembership__is_verified=True
                ),
                "lists": lists.filter(association=a),
                "entries": entries.filter(dining_list__association=a),
            }
            for a in Association.objects.order_by("name")
        }

        context.update(
            {
                "range_from": range_from,
                "range_to": range_to,
                "lists": lists,
                "users": users,
                "entries": entries,
                "per_association": per_association,
                "next": range_to + (range_to - range_from),
                "prev": range_from - (range_to - range_from),
            }
        )
        return context
