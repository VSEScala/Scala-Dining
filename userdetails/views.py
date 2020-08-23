from dal_select2.views import Select2QuerySetView
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Value
from django.db.models.functions import Concat
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import TemplateView, ListView

from dining.models import DiningEntryUser, DiningList
from userdetails.forms import RegisterUserForm, RegisterUserDetails, AssociationLinkForm
from userdetails.models import User


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


class DiningJoinHistoryView(LoginRequiredMixin, ListView):
    context = {}
    template_name = "accounts/user_history_joined.html"
    paginate_by = 20

    def get_queryset(self):
        return DiningEntryUser.objects.filter(user=self.request.user).order_by('-dining_list__date')


class DiningClaimHistoryView(LoginRequiredMixin, ListView):
    template_name = "accounts/user_history_claimed.html"
    paginate_by = 20

    def get_queryset(self):
        return DiningList.objects.filter(owners=self.request.user).order_by('-date')


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
