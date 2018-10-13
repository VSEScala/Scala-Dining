from django.shortcuts import render
from django.http import *
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views.generic import View
from datetime import datetime, timedelta
from .models import DiningList, DiningEntry, DiningEntryExternal
from .forms import create_slot_form
from .constants import MAX_SLOT_NUMBER
from UserDetails.models import AssociationDetails, UserInformation
from django.urls import reverse
from django.db.models import Q


# Create your views here.

def reverse_day(name, date, **kwargs):
    return reverse(name,
                   kwargs={'day': int(date.day),
                           'month': int(date.month),
                           'year': int(date.year), **kwargs})

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
        current_date = datetime(int(year), int(month), int(day)).date()

        if (current_date - datetime.now().date()).days == 0:
            context['is_today'] = True
        else:
            context['is_today'] = False

    else:
        current_date = datetime.now().date()
        context['is_today'] = True

    context['date'] = current_date
    context['datename'] = context['date'].strftime("%A %e %B")
    return current_date


def get_list(current_date, identifier):
    """
    Returns the dining list for the given data and identifier
    :param current_date:
    :param identifier:
    :return:
    """
    # Get the dining list by the id of the association, shorthand form of the association or the person claimed
    try:
        return DiningList.objects.get(date=current_date, association_id=identifier)
    except Exception:
        try:
            return DiningList.objects.get(date=current_date, association__associationdetails__shorthand=identifier)
        except Exception:
            try:
                return DiningList.objects.get(date=current_date, claimed_by__username=identifier)
            except Exception:
                # No proper identifier supplied
                pass


class IndexView(View):
    """"
    This is the view responsible for the day index
    Task:
    -   display all occupied dining slots
    -   allow for additional dining slots to be made if place is availlable
    """
    context = {}
    template = "dining_lists/dining_day.html"

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None):
        current_date = process_date(self.context, day, month, year)

        # Clear the message to prevent message bleeding
        self.context['message'] = None

        next_date = self.get_next_availlable_date(current_date)
        if next_date is not None:
            self.context['next_link'] = reverse_day('day_view', next_date)
        else:
            self.context['next_link'] = None

        prev_date = self.get_previous_availlable_date(current_date)
        if prev_date is not None:
            self.context['prev_link'] = reverse_day('day_view', prev_date)
        else:
            self.context['prev_link'] = None

        self.context['add_link'] = reverse_day('new_slot', current_date)
        self.context['dining_lists'] = DiningList.get_lists_on_date(current_date)

        self.context['can_create_slot'] = False
        if current_date.weekday() > 4:
            self.context['message'] = "Kitchen can't be used on weekends"
        elif len(self.context['dining_lists']) < MAX_SLOT_NUMBER:      # if maximum slots is not exceeded
            if current_date > datetime.now().date():                # if day is in the future
                    self.context['can_create_slot'] = True
            elif (current_date - datetime.now().date()).days == 0:  # if date is today
                    if datetime.now().hour < 17:                    # if it's not past 17:00
                        self.context['can_create_slot'] = True

        self.context['interactive'] = True
        return render(request, self.template, self.context)

    @staticmethod
    def get_next_availlable_date(current_date):
        max_future = 7  #Define the meaximum time one can go into the future

        next_date = current_date + timedelta(days=1)
        while next_date.weekday() > 4: #i.e. 5 or 6 which is saturday or sunday
            next_date = next_date + timedelta(days=1)

        if (next_date - datetime.now().date()).days > max_future:
            return None
        return next_date

    @staticmethod
    def get_previous_availlable_date(current_date):
        max_history = 2 #Define the maximum time one can go in the past


        prev_date = current_date - timedelta(days=1)
        while prev_date.weekday() > 4: #i.e. 5 or 6 which is saturday or sunday
            prev_date = prev_date - timedelta(days=1)
        if (prev_date - datetime.now().date()).days < -max_history:
            return None
        return prev_date


class NewSlotView(View):
    context = {}
    template = "dining_lists/dining_add.html"

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None):
        current_date = process_date(self.context, day, month, year)

        self.context['slot_form'] = create_slot_form(request.user)
        return render(request, self.template, self.context)

    def post(self, request, day=None, month=None, year=None, *args, **kwargs):
        current_date = process_date(self.context, day, month, year)

        self.context['slot_form'] = create_slot_form(request.user, info=request.POST, date=current_date)

        if not self.context['slot_form'].is_valid():
            return render(request, self.template, self.context)


        # todo set deadline date to this current date
        self.context['slot_form'].save()
        identifier = self.context['slot_form'].cleaned_data['association']
        identifier = AssociationDetails.objects.get(association__name=identifier).shorthand
        return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))


class SlotListView(View):
    context = {}
    template = "dining_lists/dining_slot_diners.html"

    def __init__(self, *args, **kwargs):
        super(SlotListView, self).__init__(*args, **kwargs)
        self.context['nav_list'] = True

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        current_date = process_date(self.context, day, month, year)

        # Get the dining list by the id of the association, shorthand form of the association or the person claimed
        self.context['dining_list'] = get_list(current_date, identifier)

        self.context['can_delete_some'] = False
        entries = []
        for entry in self.context['dining_list'].diningentry_set.all():
            entries.append(entry)
        for entry in self.context['dining_list'].diningentryexternal_set.all():
            if entry.user == request.user:
                self.context['can_delete_some'] = True
            entries.append(entry)
        from operator import methodcaller
        entries.sort(key=methodcaller('__str__'))
        self.context['entries'] = entries

        self.context['is_open'] = self.context['dining_list'].is_open()
        self.context['can_add'] = self.context['dining_list'].claimed_by == request.user
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
        for entry in dining_list.diningentry_set.all():
            if can_adjust_stats:
                entry.has_shopped = False
                entry.has_cooked = False
                entry.has_cleaned = False
            if can_adjust_paid:
                entry.has_paid = False
            entries[str(entry.id)] = entry

        # Loop over all external entries, and store them
        if can_adjust_paid:
            for entry in dining_list.diningentryexternal_set.all():
                entry.has_paid = False
                entries["E"+str(entry.id)] = entry

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


class EntryRemoveView(View):
    context = {}

    def __init__(self, *args, **kwargs):
        super(EntryRemoveView, self).__init__(*args, **kwargs)
        self.context['list'] = True

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None, id=None):
        current_date = process_date(self.context, day, month, year)
        dining_list = get_list(current_date, identifier)

        if id == None:  # The active user wants to sign out
            if request.user == dining_list.claimed_by and dining_list.diners > 1:
                # todo: handing over the dining ownership, or cancel the dining slot
                HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

            if dining_list.claimed_by is not None and \
                    datetime.now().timestamp() > dining_list.sign_up_deadline.timestamp():
                if dining_list.claimed_by != request.user:
                    # todo message: you can not remove yourself, ask the chef
                    HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

            entry = dining_list.get_entry_user(request.user)
            entry.delete()
            # todo message succes
            return HttpResponseRedirect(reverse_day('day_view', current_date))

        else:
            if not dining_list.is_open() and dining_list.claimed_by != request.user:
                # todo message: access denied, you are not the owner of the dining list and the list is closed
                return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))


            if id.startswith('E'):      # External entry
                entry = dining_list.get_entry_external(id[1:])
                if entry is None:
                    # todo message, entry does not exist
                    return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))

                if request.user != dining_list.claimed_by and request.user != entry.user:
                    # todo message: User is neither owner nor original person who added the external
                    return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))
                else:
                    entry.delete()
                    if request.user != entry.user:
                        # todo: notify user who added the external one user of removal
                        pass
                    return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))

            else:   # Object is external
                # if request was NOT added by the dininglist claimer, block access
                if request.user != dining_list.claimed_by:
                    # todo: message, you are not the dining list owner, you can not do this
                    return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

                entry = dining_list.get_entry(id)
                if entry is None:
                    # todo, entry does not exist
                    return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

                if entry.user == dining_list.claimed_by:
                    # todo: warning: removing yourself results in an unclaimed dining list
                    return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

                entry.delete()
                # todo: message succes

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
            self.context['users'] = UserInformation.objects.filter(
                Q(first_name__contains=search) |
                Q(last_name__contains=search) |
                Q(username__contains=search)
            )
            self.context['search'] = search

            if len(self.context['users'])==0:
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
    def post(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
        current_date = process_date(self.context, day, month, year)
        dining_list = get_list(current_date, identifier)

        try:
            if request.POST['button_external']:
                entry = DiningEntryExternal(dining_list=dining_list, user=request.user, name=request.POST['name'])
                entry.save()
                return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))
        except:
            pass

        try:
            if request.POST['button_user']:
                return self.get(request, day=day, month=month, year=year,
                                identifier=identifier, search=request.POST['name'])
        except:
            pass

        try:
            if request.POST['button_select']:
                user = UserInformation.objects.get(id=request.POST['user'])
                if dining_list.get_entry_user(user) is None:
                    entry = DiningEntry(dining_list=dining_list, added_by=request.user, user=user)
                    print(entry)
                    entry.save()
                return HttpResponseRedirect(reverse_day('slot_list', current_date, identifier=identifier))
        except:
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

        # If user is allready on list, inform user is already on list
        if self.context['dining_list'].get_entry_user(request.user.id) is not None:
            # user is already on the list
            return HttpResponseRedirect(reverse_day('slot_details', current_date, identifier=identifier))

        # if dining list is not open, do not add him
        if not self.context['dining_list'].is_open():
            # todo message: dining list is closed
            return HttpResponseRedirect(reverse_day('day_view', current_date))

        print(2)
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
            self.context['old_dining_list'] = entry.dining_list

            return render(request, self.template, self.context)
            pass
        else:
            # can not change to dining list
            # todo message: allready part of a closed dining list
            return HttpResponseRedirect(reverse_day('day_view', current_date))

    @method_decorator(login_required)
    def post(self, request, day=None, month=None, year=None, identifier=None, *args, **kwargs):
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
                        # todo message: you are the owner of the old dining list, this action is not allowed.
                        pass
                else:
                    # todo message: either dining list is locked, switch can not occur
                    pass
        except:
            pass

        # No is pressed
        return HttpResponseRedirect(reverse_day('day_view', current_date))


class SlotInfoView(View):
    context = {}
    template = "dining_lists/dining_slot_info.html"

    def __init__(self, *args, **kwargs):
        super(SlotInfoView, self).__init__(*args, **kwargs)
        self.context['nav_info'] = True

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None):
        current_date = process_date(self.context, day, month, year)

        # Get the dining list by the id of the association, shorthand form of the association or the person claimed
        self.context['dining_list'] = get_list(current_date, identifier)

        return render(request, self.template, self.context)

class SlotAllergyView(View):
    context = {}
    template = "dining_lists/dining_slot_allergy.html"

    def __init__(self, *args, **kwargs):
        super(SlotAllergyView, self).__init__(*args, **kwargs)
        self.context['nav_allergy'] = True

    @method_decorator(login_required)
    def get(self, request, day=None, month=None, year=None, identifier=None):
        current_date = process_date(self.context, day, month, year)

        # Get the dining list by the id of the association, shorthand form of the association or the person claimed
        self.context['dining_list'] = get_list(current_date, identifier)

        from django.db.models import CharField
        from django.db.models.functions import Length
        CharField.register_lookup(Length)
        self.context['allergy_entries'] = self.context['dining_list'].diningentry_set.filter(user__userdiningsettings__allergies__length__gt=1)

        return render(request, self.template, self.context)