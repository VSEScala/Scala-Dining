from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView, TemplateView, FormView, DetailView

from creditmanagement.csv import write_transactions_csv
from creditmanagement.forms import ClearOpenExpensesForm, SiteWideTransactionForm
from creditmanagement.models import Transaction, Account
from creditmanagement.views import TransactionFormView
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
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AssociationHasSiteAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        """Gets association and checks if user is board member."""
        if not self.association.has_site_stats_access:
            raise PermissionDenied("This association may not view this data")
        return super().dispatch(request, *args, **kwargs)


class AssociationTransactionListView(LoginRequiredMixin, AssociationBoardMixin, ListView):
    template_name = "accounts/association_credits.html"
    paginate_by = 100

    def get_queryset(self):
        return Transaction.objects.filter_account(self.association.account).order_by('-moment')


class AssociationTransactionAddView(LoginRequiredMixin, AssociationBoardMixin, TransactionFormView):
    """View where an association can transfer money to someone else."""
    template_name = 'accounts/association_credits_transaction.html'

    def get_source(self) -> Account:
        return self.association.account

    def get_success_url(self):
        return reverse('association_credits', kwargs={'association_name': self.kwargs.get('association_name')})


class AutoCreateNegativeCreditsView(LoginRequiredMixin, AssociationBoardMixin, FormView):
    template_name = "accounts/association_correct_negatives.html"
    form_class = ClearOpenExpensesForm

    def get_form_kwargs(self):
        # This view is only meant for associations with a min credit exception
        if not self.association.has_min_exception:
            raise PermissionDenied
        kwargs = super().get_form_kwargs()
        kwargs['association'] = self.association
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Member credits have successfully been processed")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('association_credits', kwargs={'association_name': self.association.slug})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Sum all transaction amounts
        context['transactions_sum'] = sum(tx.amount for tx in context['form'].transactions)
        return context


class AssociationTransactionsCSVView(LoginRequiredMixin, AssociationBoardMixin, View):
    """Returns a CSV file with all transactions."""

    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="association_transactions.csv"'
        qs = Transaction.objects.filter_account(self.association.account).order_by('-moment')
        write_transactions_csv(response, qs, self.association.account)
        return response


class MembersOverview(LoginRequiredMixin, AssociationBoardMixin, ListView):
    template_name = "accounts/association_members.html"
    paginate_by = 50

    def get_queryset(self):
        # We include inactive users who are still a member of the association.
        return User.objects.filter(
            Q(usermembership__association=self.association) & Q(usermembership__is_verified=True))


class AssociationOverview(LoginRequiredMixin, AssociationBoardMixin, TemplateView):
    template_name = "accounts/association_overview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_memberships'] = UserMembership.objects.filter(association=self.association,
                                                                       verified_on__isnull=True)
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
        redirect_to = request.GET.get('next', None)
        if url_has_allowed_host_and_scheme(redirect_to, request.get_host()):
            return HttpResponseRedirect(redirect_to)

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


class SiteDiningView(AssociationBoardMixin, AssociationHasSiteAccessMixin, DateRangeFilterMixin,
                     TemplateView):
    template_name = "accounts/site_dining_stats.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

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


class SiteCreditView(AssociationBoardMixin, AssociationHasSiteAccessMixin, TemplateView):
    """Shows an overview of the site wide credit details."""

    template_name = "accounts/site_credit.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get the balance for each association
        context['associations'] = Association.objects.all()
        context['special_accounts'] = Account.objects.filter(special__isnull=False)
        return context


class SiteTransactionView(AssociationBoardMixin, AssociationHasSiteAccessMixin, FormView):
    """View that allows creating site-wide transactions with arbitrary source.

    This is only meant to be used for the highest boss.
    """
    template_name = 'accounts/site_credit_transaction.html'
    form_class = SiteWideTransactionForm

    def get_success_url(self):
        return reverse('association_site_credit_stats', kwargs={'association_name': self.kwargs['association_name']})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save(request=self.request)
        messages.success(self.request, "The transaction has been successfully created.")
        return super().form_valid(form)


class SiteCreditDetailView(AssociationBoardMixin, AssociationHasSiteAccessMixin, DateRangeFilterMixin, DetailView):
    """Shows details for an account.

    Only allows displaying details for bookkeeping accounts.
    """
    template_name = 'accounts/site_credit_detail.html'
    model = Account
    slug_field = 'special'  # Finds the object from the 'slug' URL parameter

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = context['object']

        # Paginate transactions
        transaction_qs = account.get_transactions().order_by('-moment')
        paginator = Paginator(transaction_qs, 100)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        context['page_obj'] = page_obj

        # Handle income/outcome flow
        # We only handle and show the form if we're on page 1
        if page_obj.number == 1 and self.date_range_form.is_valid():
            qs = Transaction.objects.filter(moment__gte=self.date_start, moment__lte=self.date_end)
            influx = qs.filter(target=account).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')
            outflux = qs.filter(source=account).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00')

            context['dining_balance'] = {
                'influx': influx,
                'outflux': outflux,
                'nettoflux': influx - outflux,
            }

        return context
