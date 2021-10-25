from dal_select2.views import Select2QuerySetView
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Concat
from django.shortcuts import redirect
from django.views.generic import TemplateView, ListView

from dining.models import DiningList, DiningEntry
from userdetails.forms import CreateUserForm, AssociationLinkForm, UserForm
from userdetails.models import User


class RegisterView(TemplateView):
    template_name = "account/signup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account_form': CreateUserForm(),
            'associationlink_form': AssociationLinkForm(None),
        })
        return context

    def post(self, request, *args, **kwargs):
        user_form = CreateUserForm(request.POST)
        associationlink_form = AssociationLinkForm(None, request.POST)

        if user_form.is_valid() and associationlink_form.is_valid():
            # User is valid, safe it to the server
            with transaction.atomic():
                user = user_form.save()
                associationlink_form.save(user=user)

            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('index')

        context = self.get_context_data()
        context.update({
            'account_form': user_form,
            'associationlink_form': associationlink_form,
        })
        return self.render_to_response(context)


class DiningJoinHistoryView(LoginRequiredMixin, ListView):
    template_name = "accounts/user_history_joined.html"
    paginate_by = 20

    def get_queryset(self):
        return DiningEntry.objects.internal().filter(user=self.request.user,
                                                     dining_list__cancelled_reason="").order_by('-dining_list__date')


class DiningClaimHistoryView(LoginRequiredMixin, ListView):
    template_name = "accounts/user_history_claimed.html"
    paginate_by = 20

    def get_queryset(self):
        return DiningList.active.filter(owners=self.request.user).order_by('-date')


class PeopleAutocompleteView(LoginRequiredMixin, Select2QuerySetView):

    # django-autocomplete-light does infinite scrolling by default, but doesn't seem to trigger when paginate_by has a
    # lower value (e.g. 5)
    # paginate_by = 10

    def get_queryset(self):
        qs = User.objects.all()
        if self.q:
            qs = qs.annotate(full_name=Concat('first_name',
                                              Value(' '),
                                              'last_name')).filter(full_name__icontains=self.q)
        return qs

    def get_result_label(self, result):
        return result.get_full_name()


class SettingsProfileView(LoginRequiredMixin, TemplateView):
    # TODO: this page loads slowly and creates like >1000 queries on each page load
    #   (according to connection.queries). Need to fix this!
    template_name = "account/settings/settings_account.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'user_form': UserForm(instance=self.request.user),
            'association_links_form': AssociationLinkForm(self.request.user),
        })
        return context

    def post(self, request, *args, **kwargs):
        user_form = UserForm(request.POST, instance=self.request.user)
        association_links_form = AssociationLinkForm(self.request.user, request.POST)

        if user_form.is_valid() and association_links_form.is_valid():
            with transaction.atomic():
                user_form.save()
                association_links_form.save()
            return redirect('settings_account')

        context = self.get_context_data()
        context.update({
            'user_form': user_form,
            'association_links_form': association_links_form,
        })
        return self.render_to_response(context)
