import csv
from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import NON_FIELD_ERRORS, PermissionDenied
from django.db import transaction
from django.db.models import Q, Count
from django.http import Http404, HttpResponseRedirect, HttpResponseForbidden, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.http import is_safe_url
from django.views.generic import TemplateView, View
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import DeleteView

from dining.datesequence import sequenced_date
from dining.forms import CreateSlotForm, DiningEntryUserCreateForm, DiningEntryExternalCreateForm, \
    DiningEntryDeleteForm, DiningCommentForm, DiningInfoForm, DiningPaymentForm, DiningListDeleteForm
from dining.models import DiningList, DiningDayAnnouncement, DiningCommentVisitTracker, DiningEntryExternal, \
    DiningEntryUser, DiningEntry
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
            # Already initialized
            return
        try:
            self.date = sequenced_date.fromdate(date(self.kwargs['year'], self.kwargs['month'], self.kwargs['day']))
        except ValueError:
            raise Http404('Invalid date')

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
    """Shows the dining lists on a given date.

    Task:
    -   display all occupied dining slots
    -   allow for additional dining slots to be made if place is available
    """

    template_name = "dining_lists/dining_day.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['dining_lists'] = DiningList.objects.filter(date=self.date)
        context['Announcements'] = DiningDayAnnouncement.objects.filter(date=self.date)

        # Make the view clickable
        context['interactive'] = True

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
        context = self.get_context_data()

        context['slot_form'] = CreateSlotForm(request.user, request.POST, instance=DiningList(date=self.date))

        if context['slot_form'].is_valid():
            dining_list = context['slot_form'].save()
            messages.success(request, "You successfully created a new dining list")
            return redirect(dining_list)

        return self.render_to_response(context)


class DiningListMixin(DayMixin):
    """Mixin for a dining list detail page."""

    dining_list = None

    def get_context_data(self, **kwargs):
        context = super(DiningListMixin, self).get_context_data(**kwargs)
        context['dining_list'] = self.dining_list
        return context

    def init_dining_list(self):
        """Fetches the dining list using the request arguments."""
        if self.dining_list:
            # Already initialized
            return
        # Needs initialized date
        self.init_date()
        self.dining_list = get_object_or_404(DiningList, date=self.date, association__slug=self.kwargs['identifier'])

    def dispatch(self, request, *args, **kwargs):
        self.init_dining_list()
        return super().dispatch(request, *args, **kwargs)

    def reverse(self, *args, kwargs=None, **other_kwargs):
        kwargs = kwargs or {}
        kwargs['identifier'] = self.dining_list.association.slug
        return super().reverse(*args, kwargs=kwargs, **other_kwargs)


class UpdateSlotViewTrackerMixin:
    """Sets comments_total and comments_unread context variables."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get the amount of messages
        context['comments_total'] = self.dining_list.diningcomment_set.count()
        # Get the amount of unread messages
        view_time = DiningCommentVisitTracker.get_latest_visit(user=self.request.user, dining_list=self.dining_list)
        if view_time is None:
            context['comments_unread'] = context['comments_total']
        else:
            context['comments_unread'] = self.dining_list.diningcomment_set.filter(timestamp__gte=view_time).count()

        return context


# We use 2 different terminologies for the same thing, 'slot' and 'dining list'. We should get rid of 'slot'.

class SlotMixin(LoginRequiredMixin, DiningListMixin, UpdateSlotViewTrackerMixin):
    """Mixin for a dining list detail page."""


class EntryAddView(SlotMixin, TemplateView):
    template_name = "dining_lists/dining_entry_add.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'user_form': DiningEntryUserCreateForm(),
            'external_form': DiningEntryExternalCreateForm(),
        })
        return context

    def post(self, request, *args, **kwargs):
        # This post method always redirects, does not show the form again on validation errors, so that we don't have
        #  to write HTML for displaying these errors (they are already in a Django message).

        # Do form shenanigans
        if 'add_external' in request.POST:
            entry = DiningEntryExternal(user=request.user, dining_list=self.dining_list, created_by=request.user)
            form = DiningEntryExternalCreateForm(request.POST, instance=entry)
        else:
            entry = DiningEntryUser(dining_list=self.dining_list, created_by=request.user)
            form = DiningEntryUserCreateForm(request.POST, instance=entry)

        if form.is_valid():
            entry = form.save()
            # Construct success message
            if isinstance(entry, DiningEntryUser):
                if entry.user == request.user:
                    msg = "You successfully joined the dining list"
                else:
                    # Send mail to the diner
                    send_templated_mail('mail/dining_entry_added_by',
                                        entry.user,
                                        context={'entry': entry, 'dining_list': entry.dining_list},
                                        request=request)
                    msg = "You successfully added {} to the dining list".format(entry.user.get_short_name())
            else:
                msg = "You successfully added {} to the dining list".format(entry.name)
            messages.success(request, msg)
        else:
            # Apply error messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, "{}: {}".format(field, error) if field != NON_FIELD_ERRORS else error)

        # Redirect to next if provided, else to the diner list if successful, else to self
        next_url = request.GET.get('next')
        if next_url and is_safe_url(next_url, request.get_host()):
            return HttpResponseRedirect(next_url)
        if form.is_valid():
            # Todo: Check if user is on multiple dining lists today, then show warning?
            return HttpResponseRedirect(self.reverse('slot_list'))
        return HttpResponseRedirect(self.reverse('entry_add'))


class EntryDeleteView(LoginRequiredMixin, SingleObjectMixin, View):
    model = DiningEntry

    def post(self, request, *args, **kwargs):
        entry = self.get_object().get_subclass()

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
                context = {'entry': entry, 'dining_list': entry.dining_list, 'remover': request.user}
                if entry.is_external():
                    send_templated_mail('mail/dining_entry_external_removed_by', entry.user, context, request)
                else:
                    send_templated_mail('mail/dining_entry_removed_by', entry.user, context, request)

        else:
            for error in form.non_field_errors():
                messages.error(request, error)

        # Go to next
        next_url = request.GET.get('next')
        if not next_url or not is_safe_url(next_url, request.get_host()):
            next_url = entry.dining_list.get_absolute_url()

        return HttpResponseRedirect(next_url)


class SlotListView(SlotMixin, TemplateView):
    template_name = "dining_lists/dining_slot_diners.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Select related eliminates the extra queries during rendering of the template
        entries = self.dining_list.dining_entries.select_related('user', 'diningentryuser', 'diningentryexternal')
        entries = entries.order_by('user__first_name')
        context['entries'] = entries
        return context

    # Todo: fix complexity
    def post(self, request, *args, **kwargs):  # noqa: C901
        if not self.dining_list.is_owner(request.user):
            raise PermissionDenied

        # Check for edit conflict, not very elegant but this post method needs to be rewritten anyway
        conflict = False
        for entry in self.dining_list.dining_entries.all():
            entry = entry.get_subclass()
            if entry.is_internal():
                initial_shop = request.POST.get('initial_entry{}_shop'.format(entry.pk))
                if initial_shop and initial_shop != str(entry.has_shopped):
                    conflict = True
                    break
                initial_cook = request.POST.get('initial_entry{}_cook'.format(entry.pk))
                if initial_cook and initial_cook != str(entry.has_cooked):
                    conflict = True
                    break
                initial_clean = request.POST.get('initial_entry{}_clean'.format(entry.pk))
                if initial_clean and initial_clean != str(entry.has_cleaned):
                    conflict = True
                    break
            initial_paid = request.POST.get('initial_entry{}_paid'.format(entry.pk))
            if initial_paid and initial_paid != str(entry.has_paid):
                conflict = True
                break
        if conflict:
            messages.error(request, 'Someone else modified the stats while you were changing them, your changes have '
                                    'not been saved. We apologize for the inconvenience')
            return HttpResponseRedirect(self.reverse('slot_list'))

        # Get all the keys in the post and put all relevant ones in a list
        post_requests = []
        for key in request.POST:
            key = key.split(":")
            if len(key) == 2:
                post_requests.append(key)

        # Process payment for all entries
        entries = {}

        # For all entries in the dining list, set the paid value to false
        for entry in self.dining_list.dining_entries.all():
            entry.has_paid = False
            entries[str(entry.id)] = entry

        # Go over all keys in the request containing has_paid, adjust the state on that object
        for key in post_requests:
            if key[1] == 'has_paid':
                try:
                    entries[key[0]].has_paid = True
                except KeyError:
                    # Entry doesn't exist any more
                    pass

        # save all has_paid values
        for entry in entries.values():
            entry.save()

        # Adjust the help stats
        entries = {}

        # For all entries in the dining list, set the values to false
        for entry in self.dining_list.internal_dining_entries():
            entry.has_shopped = False
            entry.has_cooked = False
            entry.has_cleaned = False
            entries[str(entry.id)] = entry

        # Go over all keys in the request containing has_paid, adjust the state on that object
        for key in post_requests:
            try:
                if key[1] == "has_shopped":
                    entries[key[0]].has_shopped = True
                elif key[1] == "has_cooked":
                    entries[key[0]].has_cooked = True
                elif key[1] == "has_cleaned":
                    entries[key[0]].has_cleaned = True
            except KeyError:
                # Entry doesn't exist any more
                pass

        # save all has_paid values
        for entry in entries.values():
            entry.save()

        return HttpResponseRedirect(self.reverse('slot_list'))


class SlotInfoView(SlotMixin, TemplateView):
    template_name = "dining_lists/dining_slot_info.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['comments'] = self.dining_list.diningcomment_set.order_by('-pinned_to_top', 'timestamp').all()

        # Last visit
        context['last_visited'] = DiningCommentVisitTracker.get_latest_visit(
            user=self.request.user,
            dining_list=self.dining_list,
            update=True)

        from django.db.models import CharField
        from django.db.models.functions import Length
        CharField.register_lookup(Length)
        context['number_of_allergies'] = self.dining_list.internal_dining_entries().filter(
            user__userdiningsettings__allergies__length__gte=1).count()

        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)

        # Add the comment
        comment_form = DiningCommentForm(request.user, self.dining_list, data=request.POST)

        if comment_form.is_valid():
            comment_form.save()
            return HttpResponseRedirect(self.reverse('slot_details'))
        else:
            context['form'] = comment_form
            return self.render_to_response(context)


class SlotAllergyView(SlotMixin, TemplateView):
    template_name = "dining_lists/dining_slot_allergy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import CharField
        from django.db.models.functions import Length
        CharField.register_lookup(Length)
        context['allergy_entries'] = self.dining_list.internal_dining_entries().filter(
            user__userdiningsettings__allergies__length__gte=1)

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

        context.update({
            'info_form': DiningInfoForm(instance=self.dining_list, prefix='info'),
            'payment_form': DiningPaymentForm(instance=self.dining_list, prefix='payment'),
        })
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

        info_form = DiningInfoForm(request.POST, instance=self.dining_list, prefix='info')
        payment_form = DiningPaymentForm(request.POST, instance=self.dining_list, prefix='payment')

        # Save and redirect if forms are valid, stay otherwise
        if info_form.is_valid() and payment_form.is_valid():
            info_form.save()
            payment_form.save()
            messages.success(request, "Changes successfully saved")

            return HttpResponseRedirect(self.reverse('slot_details'))

        context.update({
            'info_form': info_form,
            'payment_form': payment_form,
        })

        return self.render_to_response(context)


class SlotDeleteView(SlotMixin, SlotOwnerMixin, DeleteView):
    """Page for slot deletion.

    Page is only available for slot owners.
    """
    template_name = "dining_lists/dining_slot_delete.html"
    context_object_name = "dining_list"

    def get_object(self, queryset=None):
        return self.dining_list

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        form = DiningListDeleteForm(request.user, instance)
        if form.is_valid():
            day_view_url = super(DiningListMixin, self).reverse("day_view")

            # Evaluate the query to obtain diners before the dining list is removed from the database
            to_notify = list(instance.diners.exclude(id=request.user.id))

            # Get dining list with related fields, necessary for sending mail because then the object is no longer in db
            dining_list = DiningList.objects.prefetch_related('owners', 'association').get(pk=instance.pk)

            with transaction.atomic():
                form.execute()

                # Send mail to the people on the dining list
                send_templated_mail('mail/dining_list_deleted',
                                    to_notify,
                                    {
                                        'dining_list': dining_list,
                                        'cancelled_by': request.user,
                                        'day_view_url': day_view_url
                                    },
                                    request=request)

            messages.success(request, "Dining list is deleted")

            return HttpResponseRedirect(day_view_url)

        # Could not delete
        for error in form.non_field_errors():
            messages.add_message(request, messages.ERROR, error)

        return HttpResponseRedirect(self.reverse("slot_delete"))


class SlotPaymentView(SlotMixin, SlotOwnerMixin, View):
    """A view class that allows dining list owners to send payment reminders."""

    def post(self, request, *args, **kwargs):
        unpaid_user_entries = DiningEntryUser.objects.filter(dining_list=self.dining_list, has_paid=False)
        unpaid_guest_entries = DiningEntryExternal.objects.filter(dining_list=self.dining_list, has_paid=False)

        is_reminder = datetime.now().date() > self.dining_list.date  # ?? Please explain non-trivial operations

        is_informed = False

        context = {'dining_list': self.dining_list, 'reminder': request.user, 'is_reminder': is_reminder}

        if unpaid_user_entries.count() > 0:
            send_templated_mail('mail/dining_payment_reminder',
                                User.objects.filter(diningentry__in=unpaid_user_entries),
                                context=context,
                                request=request)
            is_informed = True

        if unpaid_guest_entries.count() > 0:
            for user in User.objects.filter(diningentry__in=unpaid_guest_entries).distinct():
                guests = []

                for external_entry in unpaid_guest_entries.filter(user=user):
                    guests.append(external_entry.name)

                # Call a different message if a the user added multiple guests who hadn't paid
                # Things like this can also be done in the template
                if len(guests) == 1:
                    context["guest"] = guests[0]
                    context["guests"] = None
                else:
                    context["guest"] = None
                    context["guests"] = guests

                send_templated_mail('mail/dining_payment_reminder_external', user, context, request)

            is_informed = True

        if is_informed:
            messages.success(request, "Diners have been informed")
        else:
            messages.info(request, "There was nobody to inform, everybody has paid")

        return HttpResponseRedirect(self.reverse('slot_details'))
