from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import View, TemplateView

from UserDetails.models import User
from .forms import CreateSlotForm, DiningInfoForm, DiningPaymentForm
from .models import DiningList, DiningEntry, DiningEntryExternal, DiningDayAnnouncements, DiningComment, \
    DiningCommentView


def index(request):
    upcoming = timezone.now().date()
    # If weekend, redirect to Monday after
    if upcoming.weekday() >= 5:
        upcoming = upcoming + timedelta(days=7 - upcoming.weekday())
    return redirect('day_view', year=upcoming.year, month=upcoming.month, day=upcoming.day)


class AbstractDayView(LoginRequiredMixin, TemplateView):
    """Abstract view for a day."""

    # Stores the date for this day
    date = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Store date
        self.date = date(self.kwargs['year'], self.kwargs['month'], self.kwargs['day'])
        # Return 404 when weekend (!)
        if self.date.weekday() >= 5:
            raise Http404('Weekends are not available')
        # Add useful things to context
        context['date'] = self.date
        return context


def reverse_day(viewname, day_date, kwargs=None, **other_kwargs):
    """
    URL reverse which expands the date. See https://docs.djangoproject.com/en/2.1/ref/urlresolvers/#django.urls.reverse

    This function should maybe be moved to a better place.
    """
    kwargs = kwargs or {}
    kwargs['year'] = day_date.year
    kwargs['month'] = day_date.month
    kwargs['day'] = day_date.day
    return reverse(viewname, kwargs=kwargs, **other_kwargs)


# Todo: deprecate
def process_date(context, day, month, year):
    """
    Process the broken down date and store it in the context, returns the day as a date object
    :param context: The context object in which the data is tored
    :param day: The day of the year
    :param month: The month of the year
    :param year: The year
    :return: the date as a date object
    """
    if day is not None:
        current_date = timezone.datetime(int(year), int(month), int(day)).date()

        if (current_date - timezone.now().date()).days == 0:
            context['is_today'] = True
        else:
            context['is_today'] = False

    else:
        current_date = timezone.now().date()
        context['is_today'] = True

    context['date'] = current_date
    context['datename'] = context['date'].strftime("%A %e %B")
    return current_date


# Todo: deprecate (possibly replace with a method on DiningListManager)
def get_list(current_date, identifier):
    """
    Returns the dining list for the given date and identifier.
    """
    return DiningList.objects.get(date=current_date, association__associationdetails__shorthand=identifier)


class DayView(AbstractDayView):
    """"
    This is the view responsible for the day index
    Task:
    -   display all occupied dining slots
    -   allow for additional dining slots to be made if place is availlable
    """

    template_name = "dining_lists/dining_day.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['next_date'] = self.date + timedelta(days=3 if self.date.weekday() == 4 else 1)
        context['previous_date'] = self.date - timedelta(days=3 if self.date.weekday() == 0 else 1)

        context['dining_lists'] = DiningList.get_lists_on_date(self.date)
        context['Announcements'] = DiningDayAnnouncements.objects.filter(date=self.date)

        # Check if create slot button must be shown
        # Todo: optionally hide claim button when time is past closure time
        # (but I prefer to only check when claiming to reduce code)
        in_future = self.date >= timezone.now().date()
        context['can_create_slot'] = DiningList.objects.available_slots(self.date) >= 0 and in_future

        # Make the view clickable
        context['interactive'] = True

        return context


class NewSlotView(AbstractDayView):
    """
    Creation page for a new dining list.
    """
    template_name = "dining_lists/dining_add.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        context['slot_form'] = CreateSlotForm(self.request.user, self.date)
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


class EntryRemoveView(View):
    context = {}

    def __init__(self, *args, **kwargs):
        super(EntryRemoveView, self).__init__(*args, **kwargs)
        self.context['list'] = True

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None, user_id=None):
        current_date = process_date(self.context, day, month, year)
        dining_list = get_list(current_date, identifier)

        if user_id is None:  # The active user wants to sign out
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

        else:
            if not dining_list.is_open() and dining_list.claimed_by != request.user:
                messages.add_message(request, messages.WARNING,
                                     'Access denied: You are not the owner of the dining list and the slot is closed')
                return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))

            if user_id.startswith('E'):  # External entry
                entry = dining_list.get_entry_external(user_id[1:])
                if entry is None:
                    messages.add_message(request, messages.ERROR, 'That entry can not be removed: it does not exist')
                    return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))

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

            else:  # Object is external
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

        return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))


# todo: remove user from other lists when assigning or something
class EntryAddView(View):
    context = {}
    template = "dining_lists/dining_entry_add.html"

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None, search=None):
        current_date = process_date(self.context, day, month, year)

        # Get the dining list by the id of the association, shorthand form of the association or the person claimed
        self.context['dining_list'] = get_list(current_date, identifier)

        if search == "" or search == "User":
            search = None

        if search is not None:
            # Search all users corresponding with the typed in name
            self.context['users'] = User.objects.filter(
                Q(first_name__contains=search) |
                Q(last_name__contains=search) |
                Q(username__contains=search)
            )
            self.context['search'] = search

            if len(self.context['users']) == 0:
                self.context['error_input'] = "Error: no people with that name found"
            elif len(self.context['users']) > 10:
                self.context['error_input'] = "Error: search produced to many results"
                self.context['users'] = None
            else:
                self.context['error_input'] = None

        else:
            self.context['users'] = None
            self.context['search'] = ""
            self.context['error_input'] = None

        return render(request, self.template, self.context)

    @method_decorator(login_required)
    def post(self, request, day=None, month=None, year=None, identifier=None):
        current_date = process_date(self.context, day, month, year)
        dining_list = get_list(current_date, identifier)

        try:
            if request.POST['button_external']:
                entry = DiningEntryExternal(dining_list=dining_list, user=request.user, name=request.POST['name'])
                entry.save()
                return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))
        except:
            messages.add_message(request, messages.ERROR, 'An error occured. User has not been added')
            pass

        try:
            if request.POST['button_user']:
                return self.get(request, day=day, month=month, year=year,
                                identifier=identifier, search=request.POST['name'])
        except:
            messages.add_message(request, messages.WARNING, 'An error occured.')
            pass

        try:
            if request.POST['button_select']:
                user = User.objects.get(id=request.POST['user'])
                if dining_list.get_entry_user(user) is None:
                    entry = DiningEntry(dining_list=dining_list, added_by=request.user, user=user)
                    entry.save()
                return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))
        except:
            messages.add_message(request, messages.WARNING, 'An error occured. Uer has not been added succcesfully')
            pass

        return self.get(request, day=day, month=month, year=year, identifier=identifier, search=request.POST['name'])


class SlotJoinView(View):
    context = {}
    template = "dining_lists/dining_switch_to.html"

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None):
        current_date = process_date(self.context, day, month, year)

        # Get the dining list by the id of the association, shorthand form of the association or the person claimed
        self.context['dining_list'] = get_list(current_date, identifier)

        # If user is already on list, inform user is already on list
        if self.context['dining_list'].get_entry_user(request.user.id) is not None:
            messages.add_message(request, messages.INFO, 'You were already on this slot')
            return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

        # if dining list is not open, do not add him
        if not self.context['dining_list'].is_open():
            messages.add_message(request, messages.ERROR, 'Subscription failed: the dining list is already closed')
            return HttpResponseRedirect(reverse_day('day_view', current_date))

        if self.context['dining_list'].limit_signups_to_association_only:
            if request.user.usermemberships_set.filter(
                    association=self.context['dining_list'].association).count() == 0:
                messages.add_message(request, messages.ERROR,
                                     'Subscription failed: dining list is only for members of {0}'.format(
                                         self.context['dining_list'].assocation.details.shorthand))
                return HttpResponseRedirect(reverse_day('day_view', current_date))

        # check if user is not on other dining lists
        entries = DiningEntry.objects.filter(dining_list__date=current_date, user=request.user)
        if len(entries) == 0:
            # User is not present on another date, add user
            entry = DiningEntry(dining_list=self.context['dining_list'], user=request.user)
            entry.save()
            return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

        locked_entry = None
        for entry in entries:
            if not entry.dining_list.is_open() or entry.dining_list.claimed_by == request.user:
                # todo: if claimed by show error
                # todo, ability to cancel list on small numbers
                locked_entry = entry

        if locked_entry is None:
            # display switch template
            self.context['old_dining_list'] = locked_entry.dining_list

            return render(request, self.template, self.context)
            pass
        else:
            # can not change to dining list
            messages.add_message(request, messages.ERROR,
                                 'Addition failed: You are already part of a closed dining list')
            return HttpResponseRedirect(reverse_day('day_view', current_date))

    @method_decorator(login_required)
    def post(self, request, day=None, month=None, year=None, identifier=None):
        current_date = process_date(self.context, day, month, year)
        new_list = get_list(current_date, identifier)

        try:
            if request.POST['button_yes']:
                old_entry = DiningEntry.objects.filter(dining_list__date=current_date, user=request.user)[0]
                if new_list.is_open() and old_entry.dining_list.is_open():
                    if old_entry.dining_list.claimed_by != request.user:
                        old_entry.delete()
                        new_entry = DiningEntry(dining_list=new_list, user=request.user)
                        new_entry.save()

                        return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))
                    else:
                        messages.add_message(request, messages.ERROR, 'Action failed: you own another slot on this day')
                        pass
                else:
                    messages.add_message(request, messages.ERROR, 'Action failed: Dining list is locked')
                    pass
        except:
            pass

        # No is pressed
        return HttpResponseRedirect(reverse_day('day_view', current_date))


class SlotView(View):
    context = {}
    current_date = None

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        if day is not None:
            # If it is none, assume that date and dining list are already known
            self.current_date = process_date(self.context, day, month, year)

            # Get the dining list by the id of the association, shorthand form of the association or the person claimed
            self.context['dining_list'] = get_list(self.current_date, identifier)

        if self.context['dining_list'] is None:
            messages.add_message(request, messages.ERROR, 'Action failed: Dining list does not exist')
            return HttpResponseRedirect(reverse_day('day_view', self.current_date))

        self.context['is_open'] = self.context['dining_list'].is_open()
        self.context['user_is_on_list'] = self.context['dining_list'].get_entry_user(request.user) is not None
        self.context['user_can_add_self'] = self.context['dining_list'].can_join(request.user)
        self.context['user_can_add_others'] = self.context['dining_list'].can_join(request.user, check_for_self=False)

        # Get the amount of messages
        self.context['comments'] = self.context['dining_list'].diningcomment_set.count()
        # Get the amount of unread messages
        self.context['comments_unread'] = self.getUnreadMessages(request.user)

        return None

    @method_decorator(login_required)
    def post(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        self.current_date = process_date(self.context, day, month, year)
        self.context['dining_list'] = get_list(self.current_date, identifier)

    def getUnreadMessages(self, user):
        try:
            view_time = DiningCommentView.objects.get(user=user,
                                                      dining_list=self.context['dining_list']).timestamp
            return self.context['dining_list'].diningcomment_set.filter(timestamp__gte=view_time).count()
        except:
            return self.context['comments']


class SlotListView(SlotView):
    template = "dining_lists/dining_slot_diners.html"

    def __init__(self, *args, **kwargs):
        super(SlotListView, self).__init__(*args, **kwargs)
        self.context['tab'] = "list"

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None):
        result = super(SlotListView, self).get(request, day, month, year, identifier)
        if result is not None:
            return result

        self.context['can_delete_some'] = False
        entries = []
        for entry in self.context['dining_list'].dining_entries.all():
            entries.append(entry)
        for entry in self.context['dining_list'].dining_entries_external.all():
            if entry.user == request.user:
                self.context['can_delete_some'] = True
            entries.append(entry)
        from operator import methodcaller
        entries.sort(key=methodcaller('__str__'))
        self.context['entries'] = entries

        self.context['can_delete_some'] = self.context['can_delete_some'] * self.context['is_open']
        self.context['can_edit_stats'] = (request.user == self.context['dining_list'].claimed_by)
        self.context['can_delete_all'] = (request.user == self.context['dining_list'].claimed_by)
        purchaser = self.context['dining_list'].purchaser
        self.context['can_edit_pay'] = (request.user == purchaser or
                                        (purchaser is None and request.user == self.context['dining_list'].claimed_by))

        return render(request, self.template, self.context)

    @method_decorator(login_required)
    def post(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        current_date = process_date(self.context, day, month, year)
        dining_list = get_list(current_date, identifier)

        can_adjust_stats = request.user == dining_list.claimed_by
        can_adjust_paid = request.user == dining_list.get_purchaser()

        entries = {}
        # Loop over all user entries, and store them
        for entry in dining_list.dining_entries.all():
            if can_adjust_stats:
                entry.has_shopped = False
                entry.has_cooked = False
                entry.has_cleaned = False
            if can_adjust_paid:
                entry.has_paid = False
            entries[str(entry.id)] = entry

        # Loop over all external entries, and store them
        if can_adjust_paid:
            for entry in dining_list.dining_entries_external.all():
                entry.has_paid = False
                entries["E" + str(entry.id)] = entry

        # Loop over all keys,
        for key in request.POST:
            keysplit = key.split(":")
            if len(keysplit) != 2:
                continue

            if keysplit[0].startswith("E"):
                if keysplit[1] == "has_paid" and can_adjust_paid:
                    entries[keysplit[0]].has_paid = True
            else:
                # its a normal entry
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

        return self.get(request, day=day, month=month, year=year, identifier=identifier)


class SlotInfoView(SlotView):
    template = "dining_lists/dining_slot_info.html"

    def __init__(self, *args, **kwargs):
        super(SlotInfoView, self).__init__(*args, **kwargs)
        self.context['tab'] = "info"

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        result = super(SlotInfoView, self).get(request, day=day, month=month, year=year, identifier=identifier)
        if result is not None:
            return result

        self.context['comments'] = self.context['dining_list'].diningcomment_set.order_by('-pinned_to_top',
                                                                                          'timestamp').all()
        last_visit = DiningCommentView.objects.get_or_create(user=request.user,
                                                             dining_list=self.context['dining_list']
                                                             )[0]
        self.context['last_visited'] = last_visit.timestamp
        last_visit.timestamp = timezone.now()
        last_visit.save()

        if self.context['dining_list'].claimed_by == request.user or \
            self.context['dining_list'].purchaser == request.user:
            self.context['can_change_settings'] = True

        return render(request, self.template, self.context)

    def post(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        result = super(SlotInfoView, self).post(request, day, month, year, identifier, *args, **kwargs)
        if result is not None:
            return result

        # Add the comment
        DiningComment(dining_list=self.context['dining_list'], poster=request.user,
                      message=request.POST['comment']).save()

        return self.get(request)


class SlotInfoChangeView(SlotView):
    template = "dining_lists/dining_slot_info_alter.html"

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        result = super(SlotInfoChangeView, self).get(request, day=day, month=month, year=year, identifier=identifier)
        if result is not None:
            return result

        if self.context['dining_list'].claimed_by == request.user:
            self.context['info_form'] = DiningInfoForm(instance=self.context['dining_list'])

        if self.context['dining_list'].get_purchaser() == request.user:
            self.context['payment_form'] = DiningPaymentForm(instance=self.context['dining_list'])

        if self.context.get('info_form') is None and self.context.get('payment_form') is None:
            # User is not allowed on this page
            messages.add_message(request, messages.WARNING,
                                 'You have no permission to change the dining list info')
            return HttpResponseRedirect(reverse_day('slot_details', self.current_date, identifier=identifier))

        return render(request, self.template, self.context)

    def post(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        result = super(SlotInfoChangeView, self).post(request, day, month, year, identifier, *args, **kwargs)
        if result is not None:
            return result

        is_valid = True
        can_change = False

        self.context['payment_form'] = None

        # Check if the active user is the current user, if checked after the general info, the local object could have
        # it's information changed causing usage errors
        is_purchaser = self.context['dining_list'].get_purchaser() == request.user

        # Check general info
        if self.context['dining_list'].claimed_by == request.user:
            can_change = True
            print(request.POST)
            self.context['info_form'] = DiningInfoForm(request.POST, instance=self.context['dining_list'])
            if self.context['info_form'].is_valid():
                self.context['info_form'].save()
            else:
                is_valid = False

        if is_purchaser:
            can_change = True
            print(request.POST)
            self.context['payment_form'] = DiningPaymentForm(request.POST, instance=self.context['dining_list'])
            if self.context['payment_form'].is_valid():
                self.context['payment_form'].save()
            else:
                is_valid = False

        # Rederict if forms were all valid, stay otherwise
        if is_valid:
            if can_change:
                messages.add_message(request, messages.SUCCESS, "Changes succesfully placed")
            else:
                messages.add_message(request, messages.ERROR, "You were not allowed to change anything")

            return HttpResponseRedirect(reverse_day('slot_details', self.current_date, identifier=identifier))
        else:
            return render(request, self.template, self.context)



class SlotAllergyView(SlotView):
    template = "dining_lists/dining_slot_allergy.html"

    def __init__(self, *args, **kwargs):
        super(SlotAllergyView, self).__init__(*args, **kwargs)
        self.context['tab'] = "allergy"

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None):
        result = super(SlotAllergyView, self).get(request, day=day, month=month, year=year, identifier=identifier)
        if result is not None:
            return result

        from django.db.models import CharField
        from django.db.models.functions import Length
        CharField.register_lookup(Length)
        self.context['allergy_entries'] = self.context['dining_list'].dining_entries.filter(
            user__userdiningsettings__allergies__length__gt=1)

        return render(request, self.template, self.context)
