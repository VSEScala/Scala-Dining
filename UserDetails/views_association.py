import csv
import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import ListView, TemplateView
from django.utils.http import is_safe_url
from django.utils import timezone

from CreditManagement.models import AbstractTransaction, FixedTransaction
from .models import UserMembership, Association, User


class AssociationBoardMixin:
    """Gathers association data and verifies that the user is a board member."""
    association = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['association'] = self.association

        context['notify_overview'] = self.association.has_new_member_requests()

        return context

    def dispatch(self, request, *args, **kwargs):
        """Gets association and checks if user is board member."""
        self.association = get_object_or_404(Association, slug=kwargs['association_name'])
        if not request.user.groups.filter(id=self.association.id):
            raise PermissionDenied("You are not on the board of this association")
        return super().dispatch(request, *args, **kwargs)


class CreditsOverview(LoginRequiredMixin, AssociationBoardMixin, ListView):
    template_name = "accounts/association_credits.html"
    paginate_by = 50

    def get_queryset(self):
        return AbstractTransaction.get_all_transactions(association=self.association).order_by('-order_moment')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['balance'] = AbstractTransaction.get_association_balance(self.association)
        return context


class TransactionsCsvView(LoginRequiredMixin, AssociationBoardMixin, View):
    """Returns a CSV file with all transactions."""

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="association_transactions.csv"'
        csv_writer = csv.writer(response)
        # Write header
        csv_writer.writerow(['Created on', 'Executed on', 'Source type', 'Source name', 'Source e-mail', 'Target type',
                             'Target name', 'Target e-mail', 'Amount', 'Description'])
        # Write transactions
        for t in FixedTransaction.get_all_transactions(association=self.association):
            # Transaction moment
            moment = [t.order_moment.isoformat(), t.confirm_moment.isoformat()]
            # Transaction source
            if t.source_user:
                source = ['User', t.source_user.get_full_name(), t.source_user.email]
            elif t.source_association:
                source = ['Association', t.source_association.name, '']
            else:
                source = ['None', '', '']
            # Transaction target
            if t.target_user:
                target = ['User', t.target_user.get_full_name(), t.target_user.email]
            elif t.target_association:
                target = ['Association', t.target_association.name, '']
            else:
                target = ['None', '', '']
            # Write to CSV
            csv_writer.writerow(moment + source + target + [t.amount, t.description])
        return response


class MembersOverview(LoginRequiredMixin, AssociationBoardMixin, ListView):
    template_name = "accounts/association_members.html"
    paginate_by = 50

    def get_queryset(self):
        return User.objects.filter(
            Q(usermembership__association=self.association) & Q(usermembership__is_verified=True))


class AssociationOverview(LoginRequiredMixin, AssociationBoardMixin, TemplateView):
    template_name = "accounts/association_overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_memberships'] = UserMembership.objects.filter(association=self.association,
                                                                       verified_on__isnull=True)
        context['balance'] = AbstractTransaction.get_association_balance(self.association)
        context['transactions'] = AbstractTransaction.\
            get_all_transactions(association=self.association).\
            order_by('-order_moment')[0:5]

        return context


class MembersEditView(LoginRequiredMixin, AssociationBoardMixin, ListView):
    template_name = "accounts/association_members_edit.html"
    paginate_by = 50

    def get_queryset(self):
        return UserMembership.objects.filter(Q(association=self.association)).order_by('is_verified', 'verified_on',
                                                                                       'created_on')

    def _alter_state(self, verified, id):
        """
        Alter the state of the given usermembership
        :param verified: yes/no(!) if it should be verified or not.
        :param id: The id of the usermembershipobject
        """
        membership = UserMembership.objects.get(id=id)
        if verified == "yes":
            if membership.is_verified:
                return
            membership.set_verified(True)
        elif verified == "no":
            if not membership.is_verified and membership.verified_on is not None:
                return
            membership.set_verified(False)

    def post(self, request, *args, **kwargs):
        # Todo: there is no check on ID, i.e. any passed ID will work. I suggest switching to FormSets.
        for i in request.POST:
            # Seek if any of the validate buttons is pressed and change that state.
            if "validate" in i:
                string = i.split("-")
                verified = string[1]
                id = string[2]
                self._alter_state(verified, id)

        # If next is provided, put possible error messages on the messages system and redirect
        next = request.GET.get('next', None)
        if next and is_safe_url(next, request.get_host()):
            return HttpResponseRedirect(next)

        return HttpResponseRedirect(request.path_info)
