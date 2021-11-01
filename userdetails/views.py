from dal_select2.views import Select2QuerySetView
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Concat
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, FormView

from dining.models import DiningList, DiningEntry
from userdetails.forms import CreateUserForm, UserForm, MembershipForm
from userdetails.models import User


class RegisterView(FormView):
    template_name = "account/signup.html"
    form_class = CreateUserForm
    success_url = reverse_lazy('index')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        return super().form_valid(form)


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
            'form': UserForm(instance=self.request.user),
            'association_links_form': MembershipForm(self.request.user),
        })
        return context

    def post(self, request, *args, **kwargs):
        user_form = UserForm(request.POST, instance=self.request.user)
        membership_form = MembershipForm(self.request.user, data=request.POST)

        if user_form.is_valid() and membership_form.is_valid():
            with transaction.atomic():
                user_form.save()
                membership_form.save()
            return redirect('settings_account')

        context = self.get_context_data()
        context.update({
            'form': user_form,
            'association_links_form': membership_form,
        })
        return self.render_to_response(context)
