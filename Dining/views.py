from datetime import date, timedelta
import itertools

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect, HttpResponseForbidden, HttpResponseBadRequest

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.http import is_safe_url
from django.utils.decorators import method_decorator
from django.views.generic import View, TemplateView
from django.views.generic.edit import CreateView

from UserDetails.models import User
from .forms import CreateSlotForm, DiningInfoForm, DiningPaymentForm, DiningEntryCreateForm
from .models import DiningList, DiningEntry, DiningDayAnnouncements, DiningComment, DiningCommentView


def index(request):
    upcoming = timezone.now().date()
    # If weekend, redirect to Monday after
    if upcoming.weekday() >= 5:
        upcoming = upcoming + timedelta(days=7 - upcoming.weekday())
    return redirect('day_view', year=upcoming.year, month=upcoming.month, day=upcoming.day)


class AbstractDayView(TemplateView):
    """Adds useful thingies to context and self that have to do with the request date."""

    date = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        self.date = date(self.kwargs['year'], self.kwargs['month'], self.kwargs['day'])

        if self.date.weekday() >= 5:
            raise Http404('Weekends are not available')

        context['date'] = self.date
        context['next_date'] = self.date + timedelta(days=3 if self.date.weekday() == 4 else 1)
        context['previous_date'] = self.date - timedelta(days=3 if self.date.weekday() == 0 else 1)
        if context['next_date'] - timezone.now().date() > timedelta(days=7):
            context['next_date'] = None
        if (context['previous_date'] - timezone.now().date()).days < -2:
            context['previous_date'] = None
        context['is_today'] = (self.date - timezone.now().date()).days == 0
        return context

    def reverse(self, *args, kwargs=None, **other_kwargs):
        """
        URL reverse which expands the date. See
        https://docs.djangoproject.com/en/2.1/ref/urlresolvers/#django.urls.reverse
        """
        kwargs = kwargs or {}
        kwargs['year'] = self.date.year
        kwargs['month'] = self.date.month
        kwargs['day'] = self.date.day
        return reverse(*args, kwargs=kwargs, **other_kwargs)


class AbstractDiningListView(AbstractDayView):
    """Extends the day view with dining list thingies."""

    dining_list = None
    association_slug = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.association_slug = self.kwargs['identifier']
        self.dining_list = get_object_or_404(DiningList, date=self.date,
                                             association__associationdetails__shorthand=self.association_slug)
        context['dining_list'] = self.dining_list
        context['association_slug'] = self.association_slug
        return context

    def reverse(self, *args, kwargs=None, **other_kwargs):
        kwargs = kwargs or {}
        kwargs['identifier'] = self.association_slug
        return super().reverse(*args, kwargs=kwargs, **other_kwargs)


class DayView(LoginRequiredMixin, AbstractDayView):
    """"
    This is the view responsible for the day index
    Task:
    -   display all occupied dining slots
    -   allow for additional dining slots to be made if place is available
    """

    template_name = "dining_lists/dining_day.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['dining_lists'] = DiningList.objects.filter(date=self.date)
        context['Announcements'] = DiningDayAnnouncements.objects.filter(date=self.date)

        # Check if create slot button must be shown
        # Todo: optionally hide claim button when time is past closure time
        # (but I prefer to only check when claiming to reduce code)
        in_future = self.date >= timezone.now().date()
        context['can_create_slot'] = DiningList.objects.available_slots(self.date) >= 0 and in_future

        # Make the view clickable
        context['interactive'] = True

        return context


class NewSlotView(LoginRequiredMixin, AbstractDayView):
    """
    Creation page for a new dining list.
    """
    template_name = "dining_lists/dining_add.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        context['slot_form'] = CreateSlotForm(self.request.user, context['date'])
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()

        context['slot_form'] = CreateSlotForm(request.user, self.date, request.POST)

        # Check form validity
        if not context['slot_form'].is_valid():
            return self.render_to_response(context)

        dining_list = context['slot_form'].save()
        # Create dining entry for current user
        DiningEntry.objects.create(dining_list=dining_list, user=request.user)

        # Redirect to details page
        return redirect(dining_list)

    def dispatch(self, request, *args, year=None, month=None, day=None, **kwargs):
        """
        Disable page when no slots are available.
        """
        # Check available slots
        # Todo: DRY violation with AbstractDayView!
        # Todo: possibly also disable page when date is in the past or later than closure time!
        dining_date = date(year, month, day)
        available_slots = DiningList.objects.available_slots(dining_date)
        if available_slots <= 0:
            return HttpResponseForbidden('No available slots')
        return super().dispatch(request, *args)


class EntryAddView(LoginRequiredMixin, AbstractDiningListView):
    template_name = "dining_lists/dining_entry_add.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()

        # Search processing
        search = self.request.GET.get('search')
        if search:
            # Search all users corresponding with the typed in name
            context['users'] = User.objects.filter(
                Q(first_name__contains=search) |
                Q(last_name__contains=search) |
                Q(username__contains=search)
            )
            context['search'] = search

            if len(context['users']) == 0:
                context['error_input'] = "Error: no people with that name found"
            elif len(context['users']) > 10:
                context['error_input'] = "Error: search produced too many results"
                context['users'] = None
            else:
                context['error_input'] = None
        else:
            context['users'] = None
            context['search'] = ""
            context['error_input'] = None

        # Form rendering
        context['form'] = DiningEntryCreateForm(request.user, self.dining_list)

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()

        # Entry user defaults to current user if omitted
        post_data = request.POST.copy()
        post_data.setdefault('user', request.user.pk)

        # Do form shenanigans
        form = DiningEntryCreateForm(request.user, self.dining_list, post_data)
        if form.is_valid():
            form.save()

        # If next is provided, put possible error messages on the messages system and redirect
        next = request.GET.get('next', None)
        if next and is_safe_url(next, request.get_host()):
            for field, errors in form.errors.items():
                for error in errors:
                    messages.add_message(request, messages.ERROR, error)
            return HttpResponseRedirect(next)

        # If next not provided, but the form was valid, redirect to the slot list
        if form.is_valid():
            return HttpResponseRedirect(self.reverse('slot_list'))

        # Render form otherwise
        context['form'] = form
        return self.render_to_response(context)


class EntryRemoveView(LoginRequiredMixin, AbstractDiningListView):

    http_method_names = ['post']

    def post(self, request, *args, user_id=None, **kwargs):
        context = self.get_context_data()

        # Todo: as EntryAddView

        if user_id is None:  # The active user wants to sign out
            raise NotImplementedError("Should only use remove by id!")
            """
            if request.user == dining_list.claimed_by and dining_list.diners > 1:
                # todo: handing over the dining ownership, or cancel the dining slot
                HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

            if dining_list.claimed_by is not None and \
                    timezone.now().timestamp() > dining_list.sign_up_deadline.timestamp():
                if dining_list.claimed_by != request.user:
                    messages.add_message(request, messages.WARNING,
                                         'You can not remove yourself, ask the chef to remove you instead')
                    HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

            entry = dining_list.get_entry_user(request.user)
            entry.delete()
            messages.add_message(request, messages.SUCCESS, 'You have been removed succesfully')
            return HttpResponseRedirect(reverse_day('day_view', current_date))
            """
        else:
            if not self.dining_list.is_open() and self.dining_list.claimed_by != request.user:
                return HttpResponseForbidden("You are not the owner of the dining list and the slot is closed")

            """
            # I think this code is partially wrong (at least it's complex)
            if user_id.startswith('E'):  # External entry
                entry = dining_list.get_entry_external(user_id[1:])
                if entry is None:
                    raise Http404("Entry not found")

                if request.user != dining_list.claimed_by and request.user != entry.user:
                    messages.add_message(request, messages.WARNING,
                                         'Access denied: You did not add this entry, nor own the slot')
                    return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))
                else:
                    entry.delete()
                    if request.user != entry.user:
                        # todo: notify user who added the external one user of removal
                        pass
                    return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))

            else:  # Object is internal
                # if request was NOT added by the dininglist claimer, block access
                if request.user != dining_list.claimed_by:
                    messages.add_message(
                        request,
                        messages.ERROR,
                        'Access denied: You are not the owner of the dining list and the slot is closed')
                    return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

                entry = dining_list.get_entry(user_id)
                if entry is None:
                    messages.add_message(request, messages.ERROR, 'That entry can not be removed: it does not exist')
                    return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

                if entry.user == dining_list.claimed_by:
                    messages.add_message(request, messages.ERROR,
                                         'You can not remove yourself because you are the owner')
                    return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

                entry.delete()
                messages.add_message(request, messages.SUCCESS, '{0} removed succesfully'.format(entry.user))
            """
        return HttpResponseRedirect(self.reverse('slot_list'))


class AbstractSlotView(AbstractDiningListView):
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['is_open'] = self.dining_list.is_open()
        context['user_is_on_list'] = self.dining_list.internal_dining_entries().filter(user=self.request.user).exists()
        context['user_can_add_self'] = self.dining_list.can_join(self.request.user)
        context['user_can_add_others'] = self.dining_list.can_join(self.request.user, check_for_self=False)

        # Get the amount of messages
        context['comments'] = self.dining_list.diningcomment_set.count()
        # Get the amount of unread messages
        try:
            view_time = DiningCommentView.objects.get(user=self.request.user,
                                                      dining_list=self.dining_list).timestamp
            context['comments_unread'] = self.dining_list.diningcomment_set.filter(timestamp__gte=view_time).count()
        except DiningCommentView.DoesNotExist:
            context['comments_unread'] = context['comments']

        return context


class SlotListView(LoginRequiredMixin, AbstractSlotView):
    template_name = "dining_lists/dining_slot_diners.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tab'] = "list"
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        context['can_delete_some'] = False
        entries = []
        for entry in self.dining_list.dining_entries.all():
            entries.append(entry)
        from operator import methodcaller
        entries.sort(key=methodcaller('__str__'))
        context['entries'] = entries

        context['can_delete_some'] = context['can_delete_some'] * context['is_open']
        context['can_edit_stats'] = (request.user == self.dining_list.claimed_by)
        context['can_delete_all'] = (request.user == self.dining_list.claimed_by)
        purchaser = self.dining_list.purchaser
        context['can_edit_pay'] = (request.user == purchaser or
                                        (purchaser is None and request.user == self.dining_list.claimed_by))

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.get_context_data()

        can_adjust_stats = request.user == self.dining_list.claimed_by
        can_adjust_paid = request.user == self.dining_list.get_purchaser()

        entries = {}
        # Loop over all user entries, and store them
        for entry in self.dining_list.dining_entries.all():
            if can_adjust_stats:
                entry.has_shopped = False
                entry.has_cooked = False
                entry.has_cleaned = False
            if can_adjust_paid:
                entry.has_paid = False
            entries[str(entry.id)] = entry

        # Loop over all keys,
        for key in request.POST:
            keysplit = key.split(":")
            if len(keysplit) != 2:
                continue

            if can_adjust_stats:
                if keysplit[1] == "has_shopped":
                    entries[keysplit[0]].has_shopped = True
                elif keysplit[1] == "has_cooked":
                    entries[keysplit[0]].has_cooked = True
                elif keysplit[1] == "has_cleaned":
                    entries[keysplit[0]].has_cleaned = True
            if can_adjust_paid and keysplit[1] == "has_paid":
                entries[keysplit[0]].has_paid = True

        for entry in entries.values():
            entry.save()

        return HttpResponseRedirect(self.reverse('slot_list'))


class SlotInfoView(LoginRequiredMixin, AbstractSlotView):
    template_name = "dining_lists/dining_slot_info.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tab'] = "info"
        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()

        context['comments'] = self.dining_list.diningcomment_set.order_by('-pinned_to_top', 'timestamp').all()
        last_visit = DiningCommentView.objects.get_or_create(user=request.user, dining_list=self.dining_list)[0]
        context['last_visited'] = last_visit.timestamp
        last_visit.timestamp = timezone.now()
        last_visit.save()

        if self.dining_list.claimed_by == request.user or self.dining_list.purchaser == request.user:
            context['can_change_settings'] = True

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        self.get_context_data()

        # Add the comment
        DiningComment(dining_list=self.dining_list, poster=request.user, message=request.POST['comment']).save()

        return HttpResponseRedirect(self.reverse('slot_details'))


class SlotInfoChangeView(LoginRequiredMixin, AbstractSlotView):
    template_name = "dining_lists/dining_slot_info_alter.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()

        if self.dining_list.claimed_by == request.user:
            context['info_form'] = DiningInfoForm(instance=self.dining_list)

        if self.dining_list.get_purchaser() == request.user:
            context['payment_form'] = DiningPaymentForm(instance=self.dining_list)

        if context.get('info_form') is None and context.get('payment_form') is None:
            # User is not allowed on this page
            return HttpResponseForbidden()

        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        context = self.get_context_data()

        is_valid = True
        can_change = False

        context['payment_form'] = None

        # Check if the active user is the current user, if checked after the general info, the local object could have
        # it's information changed causing usage errors
        is_purchaser = self.dining_list.get_purchaser() == request.user

        # Check general info
        if self.dining_list.claimed_by == request.user:
            can_change = True
            context['info_form'] = DiningInfoForm(request.POST, instance=self.dining_list)
            if context['info_form'].is_valid():
                context['info_form'].save()
            else:
                is_valid = False

        if is_purchaser:
            can_change = True
            context['payment_form'] = DiningPaymentForm(request.POST, instance=self.dining_list)
            if context['payment_form'].is_valid():
                context['payment_form'].save()
            else:
                is_valid = False

        # Redirect if forms were all valid, stay otherwise
        if not can_change:
            return HttpResponseForbidden()
        elif is_valid:
            messages.add_message(request, messages.SUCCESS, "Changes successfully saved")
            return HttpResponseRedirect(self.reverse('slot_details'))

        return self.render_to_response(context)


class SlotAllergyView(LoginRequiredMixin, AbstractSlotView):
    template_name = "dining_lists/dining_slot_allergy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tab'] = "allergy"

        from django.db.models import CharField
        from django.db.models.functions import Length
        CharField.register_lookup(Length)
        context['allergy_entries'] = self.dining_list.dining_entries.filter(
            user__userdiningsettings__allergies__length__gt=1)

        return context
