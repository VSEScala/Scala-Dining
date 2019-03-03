import math

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.generic import View, FormView

from Dining.models import DiningEntryUser
from .forms import SettingsEssentialsForm, SettingsDiningForm


class DiningHistoryView(View):
    context = {}
    template = "accounts/history_dining.html"

    @method_decorator(login_required)
    def get(self, request, page=1, **kwargs):
        length = 3
        lower_bound = length * (page - 1)
        upper_bound = length * page

        # get all dining lists
        self.context['dining_entries'] = DiningEntryUser.objects.filter(user=request.user).order_by(
            '-dining_list__date')
        self.context['dining_entries_select'] = self.context['dining_entries'][lower_bound:upper_bound]
        self.context['page'] = page
        self.context['pages'] = math.ceil(len(self.context['dining_entries']) / length)
        if self.context['pages'] > 1:
            self.context['show_page_navigation'] = True
            self.context['pages'] = range(1, self.context['pages'] + 1)
        return render(request, self.template, self.context)


class SettingViewEssentials(LoginRequiredMixin, FormView):
    template_name = "accounts/settings_essentials.html"
    success_url = reverse_lazy('settings_essential')
    form_class = SettingsEssentialsForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'instance': self.request.user})
        return kwargs

    def form_valid(self, form):
        form.save()
        # Prevent the user from logging out when password has changed
        update_session_auth_hash(self.request, self.request.user)
        messages.success(self.request, _("Settings saved."))
        return super().form_valid(form)


class SettingViewDining(LoginRequiredMixin, FormView):
    template_name = "accounts/settings_dining.html"
    success_url = reverse_lazy('settings_dining')
    form_class = SettingsDiningForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'instance': self.request.user.userdiningsettings})
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, _("Settings saved."))
        return super().form_valid(form)
