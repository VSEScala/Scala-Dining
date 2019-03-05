import math

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.utils.translation import gettext as _

from Dining.models import DiningEntryUser
from .forms import RegisterUserForm, RegisterUserDetails, RegisterAssociationLinks, UserForm, DiningProfileForm
from .models import User


class RegisterView(TemplateView):
    template_name = "account/signup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account_form': RegisterUserForm(),
            'account_detail_form': RegisterUserDetails(),
            'associationlink_form': RegisterAssociationLinks(),
        })
        return context

    def post(self, request, *args, **kwargs):
        account_form = RegisterUserForm(request.POST)
        account_detail_form = RegisterUserDetails(request.POST)
        associationlink_form = RegisterAssociationLinks(request.POST)

        context = {
            'account_form': account_form,
            'account_detail_form': account_detail_form,
            'associationlink_form': associationlink_form,
        }

        if account_form.is_valid() and account_detail_form.is_valid() and associationlink_form.is_valid():
            # User is valid, safe it to the server
            user = account_form.save()
            user = User.objects.get(pk=user.pk)
            account_detail_form.save_as(user)
            associationlink_form.create_links_for(user)

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return HttpResponseRedirect(reverse('index'))

        return self.render_to_response(context)


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



