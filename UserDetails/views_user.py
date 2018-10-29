from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.views.generic import View
from .forms import Settings_Essentials_Form, Settings_Dining_Form
import math

from Dining.models import DiningList, DiningEntry
from CreditManagement.models import Transaction

class DiningHistoryView(View):
    context = {}
    template = "accounts/history_dining.html"

    @method_decorator(login_required)
    def get(self, request, page=1, **kwargs):
        length = 3
        lower_bound = length * (page - 1)
        upper_bound = length * page

        # get all dining lists
        self.context['dining_entries'] = DiningEntry.objects.filter(user=request.user).order_by('-dining_list__date')
        self.context['dining_entries_select'] = self.context['dining_entries'][lower_bound:upper_bound]
        self.context['page'] = page
        self.context['pages'] = math.ceil(len(self.context['dining_entries']) / length)
        if self.context['pages'] > 1:
            self.context['show_page_navigation'] = True
            self.context['pages'] = range(1, self.context['pages']+1)
        return render(request, self.template, self.context)

class CreditsOverview(View):
    context = {}
    template = "accounts/history_credits.html"

    @method_decorator(login_required)
    def get(self, request, page=1):
        length = 5
        lower_bound = length * (page - 1)
        upper_bound = length * page

        dining_lists = DiningList.objects.filter(diningentry__user=request.user)
        dining_lists = DiningList.objects.filter(diningentryexternal__user=request.user).union(dining_lists)

        transactions = Transaction.objects.filter(source_user=request.user, source_association=None)
        transactions = Transaction.objects.filter(target_user=request.user, target_association=None).union(transactions)

        entries = []
        for entry in dining_lists:
            entry.totalcost = 0

            # Get if the member is part of the dininglist
            entry.is_member = entry.get_entry_user(request.user.id) is not None
            if entry.is_member:
                entry.totalcost -= entry.get_credit_cost()

            # Get all the external entries
            entry.ext_members = entry.diningentryexternal_set.filter(user=request.user)
            if len(entry.ext_members) > 0:
                entry.totalcost -= entry.get_credit_cost() * len(entry.ext_members)
                entry.has_externals = True

            # Correct if autopay is enabled and user is the purchaser
            if entry.auto_pay and entry.get_purchaser() == request.user:
                entry.gain_money = True
                entry.totalcost += entry.dinner_cost_total

            if entry.totalcost < 0:
                entry.subtract = True
                entry.totalcost = entry.totalcost * -1


            entries.append(entry)
        for entry in transactions:
            entries.append(entry)

        import operator
        entries.sort(key=operator.attrgetter('date'), reverse=True)

        self.context['entries'] = entries[lower_bound:upper_bound]
        self.context['page'] = page
        self.context['pages'] = math.ceil(len(entries) / length)
        self.context['target'] = request.user
        if self.context['pages'] > 1:
            self.context['show_page_navigation'] = True
            self.context['pages'] = range(1, self.context['pages']+1)


        return render(request, self.template, self.context)


class SettingsView(View):
    context = {}
    template = "accounts/settings_base.html"

    @method_decorator(login_required)
    def get(self, request):

        return render(request, self.template, self.context)


class SettingView_Essentials(View):
    context = {}
    template = "accounts/settings_essentials.html"
    context['tab_account'] = True

    @method_decorator(login_required)
    def get(self, request):
        self.context['form'] = Settings_Essentials_Form(instance=request.user)

        return render(request, self.template, self.context)

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        self.context['form'] = Settings_Essentials_Form(request.POST, instance=request.user)

        if self.context['form'].is_valid():
            self.context['form'].save()
            update_session_auth_hash(request, request.user)
            return self.get(request)

        return render(request, self.template, self.context)


class SettingView_Dining(View):
    context = {}
    template = "accounts/settings_dining.html"
    context['tab_dining'] = True

    @method_decorator(login_required)
    def get(self, request):
        self.context['form'] = Settings_Dining_Form(instance=request.user.userdiningsettings)

        return render(request, self.template, self.context)

    @method_decorator(login_required)
    def post(self, request, *args, **kwargs):
        self.context['form'] = Settings_Dining_Form(request.POST, instance=request.user.userdiningsettings)

        if self.context['form'].is_valid():
            self.context['form'].save()
            return self.get(request)

        return render(request, self.template, self.context)

