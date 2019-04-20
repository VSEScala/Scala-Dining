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

from Dining.models import DiningEntryUser, DiningList
from General.views import PageListMixin
from .forms import RegisterUserForm, RegisterUserDetails, AssociationLinkForm
from .models import User


class RegisterView(TemplateView):
    template_name = "account/signup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account_form': RegisterUserForm(),
            'account_detail_form': RegisterUserDetails(),
            'associationlink_form': AssociationLinkForm(None),
        })
        return context

    def post(self, request, *args, **kwargs):
        account_form = RegisterUserForm(request.POST)
        account_detail_form = RegisterUserDetails(request.POST)
        associationlink_form = AssociationLinkForm(None, request.POST)

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
            associationlink_form.save(user=user)

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return HttpResponseRedirect(reverse('index'))

        return self.render_to_response(context)


class DiningJoinHistoryView(View, PageListMixin):
    context = {}
    template = "accounts/user_history_joined.html"

    @method_decorator(login_required)
    def get(self, request, page=1, **kwargs):

        entries = DiningEntryUser.objects.filter(user=request.user).order_by('-dining_list__date')
        super().set_up_list(entries, page)
        return render(request, self.template, self.context)


class DiningClaimHistoryView(View, PageListMixin):
    context = {}
    template = "accounts/user_history_claimed.html"

    @method_decorator(login_required)
    def get(self, request, page=1, **kwargs):

        from django.db.models import Q
        entries = DiningList.objects.filter(Q(claimed_by=request.user) | Q(purchaser=request.user)).order_by('-date')
        super().set_up_list(entries, page)
        return render(request, self.template, self.context)



