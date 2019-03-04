import math

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.contrib import messages

from Dining.models import DiningEntryUser
from .forms import Settings_Essentials_Form, Settings_Dining_Form


class DiningHistoryView(View):
    context = {}
    template = "accounts/history_dining.html"

    @method_decorator(login_required)
    def get(self, request, page=1, **kwargs):
        length = 3
        lower_bound = length * (page - 1)
        upper_bound = length * page

        # get all dining lists
        self.context['dining_entries'] = DiningEntryUser.objects.filter(user=request.user).order_by('-dining_list__date')
        self.context['dining_entries_select'] = self.context['dining_entries'][lower_bound:upper_bound]
        self.context['page'] = page
        self.context['pages'] = math.ceil(len(self.context['dining_entries']) / length)
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
            messages.add_message(request, messages.SUCCESS, "Succesfully altered settings")

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
            messages.add_message(request, messages.SUCCESS, "Succesfully altered settings")
            return self.get(request)

        return render(request, self.template, self.context)

