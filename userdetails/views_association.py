import csv
import decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Count, Sum
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.http import is_safe_url
from django.views import View
from django.views.generic import ListView, TemplateView, FormView

from creditmanagement.forms import ClearOpenExpensesForm
from creditmanagement.models import AbstractTransaction, FixedTransaction
from dining.models import DiningList, DiningEntry
from general.views import DateRangeFilterMixin
from userdetails.forms import AssociationSettingsForm
from userdetails.models import UserMembership, Association, User


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


class AssociationHasSiteAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        """Gets association and checks if user is board member."""
        if not self.association.has_site_stats_access:
            raise PermissionDenied("This association may not view this data")
        return super(AssociationHasSiteAccessMixin, self).dispatch(request, *args, **kwargs)


class CreditsOverview(LoginRequiredMixin, AssociationBoardMixin, ListView):
    template_name = "accounts/association_credits.html"
    paginate_by = 50

    def get_queryset(self):
        return AbstractTransaction.get_all_transactions(association=self.association).order_by('-order_moment')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['balance'] = AbstractTransaction.get_association_balance(self.association)
        return context


class AutoCreateNegativeCreditsView(LoginRequiredMixin, AssociationBoardMixin, FormView):
    template_name = "accounts/association_correct_negatives.html"
    form_class = ClearOpenExpensesForm

    def get_form_kwargs(self):
        kwargs = super(AutoCreateNegativeCreditsView, self).get_form_kwargs()
        kwargs['association'] = self.association
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, 'Member credits have successfully been processed')
        return super(AutoCreateNegativeCreditsView, self).form_valid(form)

    def get_success_url(self):
        return reverse('association_credits', kwargs={'association_name': self.association.slug})


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
        context['transactions'] = AbstractTransaction.get_all_transactions(
            association=self.association).order_by('-order_moment')[0:5]

        return context


class MembersEditView(LoginRequiredMixin, AssociationBoardMixin, ListView):
    template_name = "accounts/association_members_edit.html"
    paginate_by = 50

    def get_queryset(self):
        return UserMembership.objects.filter(Q(association=self.association)).order_by('is_verified', 'verified_on',
                                                                                       'created_on')

    def _alter_state(self, verified, id):
        """Alter the state of the given user membership.

        :param verified: yes/no(!) if it should be verified or not.
        :param id: The id of the usermembership object.
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


class AssociationSettingsView(AssociationBoardMixin, TemplateView):
    template_name = "accounts/association_settings.html"

    def get_context_data(self, **kwargs):
        context = super(AssociationSettingsView, self).get_context_data(**kwargs)
        context['form'] = AssociationSettingsForm(instance=self.association)

        return context

    def post(self, request, association_name=None):
        # Do form shenanigans
        form = AssociationSettingsForm(data=request.POST, instance=self.association)

        if form.is_valid():
            form.save()
            messages.add_message(request, messages.SUCCESS, "Changes successfully saved.")
            return HttpResponseRedirect(request.path_info)

        context = self.get_context_data()
        context['form'] = form
        return render(request, self.template_name, context)


class AssociationSiteDiningView(AssociationBoardMixin, AssociationHasSiteAccessMixin, DateRangeFilterMixin,
                                TemplateView):
    template_name = "accounts/association_site_dining_stats.html"

    def get_context_data(self, **kwargs):
        context = super(AssociationSiteDiningView, self).get_context_data(**kwargs)

        if self.date_range_form.is_valid():
            dining_lists = DiningList.objects.filter(date__gte=self.date_start, date__lte=self.date_end)
            association_stats = {}

            # Get general data for each association
            for association in Association.objects.all():
                # Some general statistics
                cooked_for = DiningEntry.objects.filter(
                    dining_list__association=association,
                    dining_list__in=dining_lists)
                memberships = UserMembership.objects.filter(association=association, is_verified=True)
                members = User.objects.filter(usermembership__in=memberships)

                cooked_for_own = cooked_for.filter(user__in=members)

                association_stats[association.id] = {
                    'association': association,
                    'lists_claimed': dining_lists.filter(association=association).count(),
                    'cooked_for': cooked_for.count(),
                    'cooked_for_own': cooked_for_own.count(),
                    'weighted_eaters': 0,
                }
            # Get general data for all members. Note: this is done here as the length of members is significantly longer
            # than the number of associations so this should be quicker
            users = User.objects.filter(diningentry__dining_list__in=dining_lists).annotate(
                dining_entry_count=Count('diningentry'))

            for user in users:
                memberships = UserMembership.objects.filter(is_verified=True, related_user=user)
                if memberships:
                    user_weight = user.dining_entry_count / memberships.count()

                    for membership in memberships:
                        association_stats[membership.association_id]['weighted_eaters'] += user_weight
            context['stats'] = association_stats
        return context


class AssociationSiteCreditView(AssociationBoardMixin, AssociationHasSiteAccessMixin, DateRangeFilterMixin,
                                TemplateView):
    template_name = "accounts/association_site_credit_stats.html"

    def get_context_data(self, **kwargs):
        context = super(AssociationSiteCreditView, self).get_context_data(**kwargs)

        # Get the balance for each association
        association_stats = {}
        for association in Association.objects.all():
            association_stats[association.id] = {
                'association': association,
                'balance': AbstractTransaction.get_association_balance(association),
            }
        context['association_balances'] = association_stats

        # Get the income through the dining list
        if self.date_range_form.is_valid():
            transactions = FixedTransaction.objects. \
                filter(confirm_moment__gte=self.date_start,
                       confirm_moment__lte=self.date_end)
            # Aggregate the values
            influx = transactions.filter(
                target_user__isnull=True,
                target_association__isnull=True
            ).aggregate(sum=Sum('amount'))['sum']

            outflux = transactions.filter(
                source_user__isnull=True,
                source_association__isnull=True
            ).aggregate(sum=Sum('amount'))['sum']

            if influx is None:
                influx = 0
            influx = decimal.Decimal(influx)

            if outflux is None:
                outflux = 0
            outflux = decimal.Decimal(outflux)

            context['dining_balance'] = {
                'influx': influx.quantize(decimal.Decimal('.01')),
                'outflux': outflux.quantize(decimal.Decimal('.01')),
                'nettoflux': (influx - outflux).quantize(decimal.Decimal('.01'))
            }
        return context
