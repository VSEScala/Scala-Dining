import csv
from datetime import date, datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied
from django.db.models import Q, Count
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView, View, DeleteView
from django.views.generic.detail import SingleObjectMixin

from dining.datesequence import sequenced_date
from dining.forms import CreateSlotForm, DiningEntryInternalCreateForm, DiningEntryExternalCreateForm, \
    DiningEntryDeleteForm, DiningCommentForm, DiningInfoForm
from dining.models import DiningList, DiningDayAnnouncement, DiningCommentVisitTracker, DiningEntry
from general.mail_control import send_templated_mail
from userdetails.models import User, Association


def index(request):
    d = sequenced_date.upcoming()
    return redirect('day_view', year=d.year, month=d.month, day=d.day)


class DayMixin:
    """Adds useful thingies to context and self that have to do with the request date."""

    date = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['date'] = self.date
        # Nr of days between date and today
        context['date_diff'] = (self.date - date.today()).days
        return context

    def init_date(self):
        """Fetches the date from the request arguments."""
        if self.date:
            return  # Already initialized
        self.date = sequenced_date(self.kwargs['year'], self.kwargs['month'], self.kwargs['day'])

    def dispatch(self, request, *args, **kwargs):
        """Initializes date before get/post is called."""
        self.init_date()
        return super().dispatch(request, *args, **kwargs)

    def reverse(self, *args, kwargs=None, **other_kwargs):
        """URL reverse which expands the date."""
        kwargs = kwargs or {}
        kwargs['year'] = self.date.year
        kwargs['month'] = self.date.month
        kwargs['day'] = self.date.day
        return reverse(*args, kwargs=kwargs, **other_kwargs)


class DayView(LoginRequiredMixin, DayMixin, TemplateView):
    """Shows the dining lists on a given date."""

    template_name = "dining_lists/day.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        context.update({
            'dining_lists': DiningList.objects.filter(date=self.date),
            'announcements': DiningDayAnnouncement.objects.filter(date=self.date),
            'available_slots': DiningList.objects.available_slots(self.date),
            # Whether this day is in the future
            'creation_open': self.date > now.date() or (
                    self.date == now.date() and settings.DINING_SLOT_CLAIM_CLOSURE_TIME < now.time()),  # noqa: E126
        })
        return context


class DailyDinersCSVView(LoginRequiredMixin, View):
    """Returns a CSV file with all diners of that day."""

    def get(self, request, *args, **kwargs):

        # Only superusers can access this page
        if not request.user.is_superuser:
            return HttpResponseForbidden

        # Get the end date
        date_end = request.GET.get('to', None)
        if date_end:
            # Why do you use datetime here and not date?
            date_end = datetime.strptime(date_end, '%d/%m/%y')
        else:
            date_end = timezone.now()

        # Filter on a start date
        date_start = request.GET.get('from', None)
        if date_start:
            date_start = datetime.strptime(date_start, '%d/%m/%y')
        else:
            date_start = date_end

        # Count all dining entries in the given period
        entry_count = Count('diningentry', filter=(Q(diningentry__dining_list__date__lte=date_end) & Q(
            diningentry__dining_list__date__gte=date_start)))

        # Annotate the counts to the user
        users = User.objects.annotate(diningentry_count=entry_count)
        users = users.filter(diningentry_count__gt=0)

        # Get the related membership objects for speed optimisation
        users.select_related('usermembership')

        # Get all associations
        associations = Association.objects.all()

        # Create the CSV file
        # Set up
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="association_members.csv"'
        csv_writer = csv.writer(response)

        # Write header
        header = ['Name', 'Joined']
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
        context.update({
            'slot_form': CreateSlotForm(self.request.user, instance=DiningList(date=self.date))
        })
        return context

    def post(self, request, *args, **kwargs):
        form = CreateSlotForm(request.user, data=request.POST, instance=DiningList(date=self.date))

        if form.is_valid():
            dining_list = form.save()
            return redirect(dining_list)
        context = self.get_context_data()
        context.update({
            'slot_form': form,
        })
        return self.render_to_response(context)


class DiningListMixin(SingleObjectMixin):
    """Mixin for a dining list detail page."""
    model = DiningList
    context_object_name = 'dining_list'

    def get_context_data(self, **kwargs):
        self.object = self.get_object()
        """This is apparently needed for SingleObjectMixin, see docs:

        > The base implementation of this method requires that the self.object attribute be set by the view (even if
        > None). Be sure to do this if you are using this mixin without one of the built-in views that does so.
        """
        return super().get_context_data(**kwargs)


class DiningListEditMixin(UserPassesTestMixin, DiningListMixin):
    """Dining list mixin which makes a view only accessible if the dining list can be edited."""

    def test_func(self):
        # Checks if the user is owner and if the dining list is adjustable
        dining_list = self.get_object()  # type: DiningList
        return dining_list.is_owner(self.request.user) and dining_list.is_adjustable()


# We use 2 different terminologies for the same thing, 'slot' and 'dining list'. We should get rid of 'slot'.


class EntryAddView(LoginRequiredMixin, DiningListMixin, TemplateView):
    template_name = "dining_lists/dining_entry_add.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'user_form': DiningEntryInternalCreateForm(),
            'external_form': DiningEntryExternalCreateForm(),
        })
        return context

    def post(self, request, *args, **kwargs):
        # This post method always redirects, does not show the form again on validation errors, so that we don't have
        #  to write HTML for displaying these errors (they are already in a Django message).
        dining_list = self.get_object()

        # Do form shenanigans
        if 'add_external' in request.POST:
            entry = DiningEntry(user=request.user, dining_list=dining_list, created_by=request.user)
            form = DiningEntryExternalCreateForm(data=request.POST, instance=entry)
        else:
            entry = DiningEntry(dining_list=dining_list, created_by=request.user)
            form = DiningEntryInternalCreateForm(data=request.POST, instance=entry)

        if form.is_valid():
            entry = form.save()

            # Other existing user, send mail
            if entry.is_internal() and entry.user != request.user:
                send_templated_mail('mail/dining_entry_added_by',
                                    entry.user,
                                    context={'entry': entry, 'dining_list': entry.dining_list},
                                    request=request)
                messages.success(request,
                                 "You successfully added {} to the dining list".format(entry.user.get_short_name()))

            # External entry
            if entry.is_external():
                messages.success(request, "You successfully added {} to the dining list".format(entry.external_name))
        else:
            # Apply error messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, "{}: {}".format(field, error) if field != NON_FIELD_ERRORS else error)

        # Always redirect to the dining list page
        return redirect(dining_list)


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
                pass
            elif entry.is_external():
                messages.success(request, "The external diner is removed from the dining list")
            else:
                messages.success(request, "The user is removed from the dining list")

            # Send a mail when someone else does the removal
            if entry.user != request.user:
                context = {'entry': entry, 'dining_list': entry.dining_list, 'remover': request.user}
                if entry.is_external():
                    send_templated_mail('mail/dining_entry_external_removed_by', entry.user, context, request)
                else:
                    send_templated_mail('mail/dining_entry_removed_by', entry.user, context, request)

        else:
            for error in form.non_field_errors():
                messages.error(request, error)

        # Go to dining list page
        return redirect(entry.dining_list)


class SlotListView(LoginRequiredMixin, DiningListMixin, TemplateView):
    template_name = "dining_lists/dining_slot_diners.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dl = self.get_object()  # type: DiningList
        context.update({
            'entries': dl.entries.order_by('user__first_name', 'user__last_name'),
            'can_edit_stats': dl.is_owner(self.request.user) and dl.is_adjustable(),
            # Contact info is visible to diners and owners
            'show_contact_info': (self.request.user in dl.diners.all()) or dl.is_owner(self.request.user),

        })
        return context

    def post(self, request, *args, **kwargs):
        dining_list = self.get_object()  # type: DiningList

        # To change help stats, the user needs to be owner and the list needs to be adjustable
        if not dining_list.is_owner(request.user) or not dining_list.is_adjustable():
            raise PermissionDenied

        # Get the internal entry by ID, also provide the dining list to check that the entry belongs to this list
        entry = get_object_or_404(DiningEntry, id=request.POST.get('entry_id'), dining_list=dining_list)

        # Apply action
        action = request.POST.get('action')  # type: str
        val = action.endswith('true')
        if action.startswith('shopped'):
            entry.has_shopped = val
        elif action.startswith('cooked'):
            entry.has_cooked = val
        elif action.startswith('cleaned'):
            entry.has_cleaned = val

        entry.save()
        return redirect('slot_list', pk=dining_list.pk)


class SlotInfoView(LoginRequiredMixin, DiningListMixin, TemplateView):
    template_name = "dining_lists/dining_slot_info.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dining_list = self.get_object()  # type: DiningList

        context.update({
            'comments': dining_list.diningcomment_set.order_by('-pinned_to_top', 'timestamp').all(),
            'user_entry': DiningEntry.objects.internal().filter(dining_list=dining_list,
                                                                user=self.request.user).first(),
            'last_visited': DiningCommentVisitTracker.get_latest_visit(user=self.request.user,
                                                                       dining_list=dining_list,
                                                                       update=True),
        })

        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        dining_list = self.get_object()

        # Add the comment
        comment_form = DiningCommentForm(request.user, dining_list, data=request.POST)

        if comment_form.is_valid():
            comment_form.save()
            return redirect('slot_details', pk=dining_list.pk)
        else:
            context['form'] = comment_form
            return self.render_to_response(context)


class SlotAllergyView(LoginRequiredMixin, DiningListMixin, TemplateView):
    template_name = "dining_lists/dining_slot_allergy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dining_list = self.get_object()
        context.update({
            'entries': dining_list.internal_dining_entries().exclude(user__dietary_requirements=""),
        })
        return context


class DiningListChangeView(LoginRequiredMixin, DiningListEditMixin, TemplateView):
    template_name = "dining_lists/change.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'form': DiningInfoForm(instance=self.get_object()),
            # Sign up deadline preset buttons
            'deadline_presets': {
                'closed': timezone.now(),
                'open for 15 minutes': timezone.now() + timedelta(minutes=15),
            }
        })
        return context

    def post(self, request, *args, **kwargs):
        dining_list = self.get_object()

        form = DiningInfoForm(request.POST, instance=dining_list)
        if form.is_valid():
            form.save()
            return redirect(dining_list)

        context = self.get_context_data(**kwargs)
        context.update({
            'form': form,
        })
        return self.render_to_response(context)


class DiningListDeleteView(LoginRequiredMixin, DiningListEditMixin, DeleteView):
    template_name = 'dining_lists/confirm_delete.html'

    def get_success_url(self):
        d = self.object.date  # type: date
        return reverse('day_view', kwargs={'year': d.year, 'month': d.month, 'day': d.day})
