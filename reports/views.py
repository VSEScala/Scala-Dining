from decimal import Decimal

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import BadRequest
from django.db.models import Case, Sum, When
from django.utils.timezone import localdate
from django.views.generic import DetailView, TemplateView

from creditmanagement.models import Account, Transaction
from reports.period import Period, QuarterPeriod
from userdetails.models import Association


class ReportAccessMixin(UserPassesTestMixin):
    def test_func(self):
        # TODO rewrite to self.request.user.has_site_stats_access() when PR #276 is merged
        boards = Association.objects.filter(user=self.request.user)
        return True in (b.has_site_stats_access for b in boards)


class ReportsView(ReportAccessMixin, TemplateView):
    template_name = "reports/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "association_accounts": Account.objects.filter(
                    association__isnull=False
                ).order_by("association__name"),
                "bookkeeping_accounts": Account.objects.filter(special__isnull=False),
            }
        )
        return context


class PeriodMixin:
    """Mixin for yearly reporting periods."""

    def get_year(self):
        try:
            return int(self.request.GET.get("year", localdate().year))
        except ValueError:
            raise BadRequest

    def get_periods(self) -> list[Period]:
        return QuarterPeriod.for_year(self.get_year())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["year"] = self.get_year()
        return context


class BalanceView(ReportAccessMixin, PeriodMixin, TemplateView):
    """Periodical reports of the balance of all credit accounts.

    User accounts are aggregated as one large pile. Association and bookkeeping
    accounts are shown individually.
    """

    template_name = "reports/balance.html"

    def get_report(self):
        """Computes the report values."""
        periods = self.get_periods()

        # Compute opening balance
        running_balance = {
            account: increase - reduction
            for account, (increase, reduction) in Transaction.objects.filter(
                moment__lt=periods[0].get_period_start()
            )
            .sum_by_account(group_users=True)
            .items()
        }

        report = []
        for period in periods:
            # Compute credit and debit sum in the period
            mutation = period.get_transactions().sum_by_account(group_users=True)

            # Compile report for this period
            statements = {
                account: {
                    "start_balance": running_balance.get(account, Decimal("0.00")),
                    "increase": increase,
                    "reduction": reduction,
                    "end_balance": running_balance.get(account, Decimal("0.00"))
                    + increase
                    - reduction,
                }
                for account, (increase, reduction) in mutation.items()
            }

            # Update running balance
            running_balance.update(
                (account, val["end_balance"]) for account, val in statements.items()
            )

            report.append((period, statements))
        return report

    def get_context_data(self, **kwargs):
        # This function just regroups and sorts the values for display

        context = super().get_context_data(**kwargs)

        # For the template: retrieve each Account instance, regroup by type and sort
        report_display = []
        account = {}  # Cache for Account lookups

        for period, statements in self.get_report():
            # Retrieve Accounts from database
            for pk in statements:
                if pk is not None and pk not in account:
                    account[pk] = Account.objects.get(pk=pk)

            # Split by type
            bookkeeping = []
            association = []
            user_pile = None
            for pk, statement in statements.items():
                if pk is None:
                    user_pile = statement
                elif account[pk].special:
                    bookkeeping.append((account[pk], statement))
                elif account[pk].association:
                    association.append((account[pk], statement))
                else:
                    raise RuntimeError  # Unreachable

            # Sort bookkeeping and association by name
            bookkeeping.sort(key=lambda e: e[0].special)
            association.sort(key=lambda e: e[0].association.name)

            report_display.append((period, bookkeeping, association, user_pile))

        context["report_display"] = report_display
        return context


class CashFlowView(ReportAccessMixin, PeriodMixin, DetailView):
    """Periodical reports of money entering and leaving a specific account.

    For a selected account, shows the flow of money to and from other accounts
    in a certain period.
    """

    template_name = "reports/cashflow.html"
    model = Account
    context_object_name = "account"

    def get_period_statement(self, period):
        """Returns a dictionary from Account or None to an income/outgoings tuple."""
        tx = period.get_transactions()
        # Aggregate income and outgoings
        income = (
            tx.filter(target=self.object)
            # Set the group key to NULL for all user accounts
            .annotate(
                account=Case(
                    When(source__user__isnull=False, then=None),
                    default="source",
                )
            )
            # Group by source account
            .values("account")
            # Sum amount for each separate source
            .annotate(sum=Sum("amount"))
        )
        outgoings = (
            # See above for income
            tx.filter(source=self.object)
            .annotate(
                account=Case(
                    When(target__user__isnull=False, then=None),
                    default="target",
                )
            )
            .values("account")
            .annotate(sum=Sum("amount"))
        )

        # Regroup on account
        income = {v["account"]: v["sum"] for v in income}
        outgoings = {v["account"]: v["sum"] for v in outgoings}
        regroup = {
            # Retrieve Account from db
            Account.objects.get(pk=account)
            if account
            else None: (
                income.get(account),
                outgoings.get(account),
            )
            for account in income.keys() | outgoings.keys()
        }
        print(regroup)
        return regroup

    def get_report(self):
        return [(p, self.get_period_statement(p)) for p in self.get_periods()]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_display = []
        for period, statements in self.get_report():
            # Convert to list of tuples
            statements2 = [
                (account, inc, out) for account, (inc, out) in statements.items()
            ]
            # Sort in 3 steps to have first the bookkeeping accounts in
            # alphabetical order, then the association accounts in order and
            # then the user pile.
            #
            # This works because sort is stable.
            statements2.sort(
                key=lambda v: v[0].association.name if v[0] and v[0].association else ""
            )
            statements2.sort(
                key=lambda v: v[0].special if v[0] and v[0].special else ""
            )
            statements2.sort(
                key=lambda v: 2 if v[0] is None else 1 if v[0].association else 0
            )

            report_display.append((period, statements2))
        context["report_display"] = report_display
        return context


class CashFlowIndexView(ReportAccessMixin, TemplateView):
    template_name = "reports/cashflow_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "association_accounts": Account.objects.filter(
                    association__isnull=False
                ).order_by("association__name"),
                "bookkeeping_accounts": Account.objects.filter(special__isnull=False),
            }
        )
        return context


class TransactionsReportView(ReportAccessMixin, PeriodMixin, TemplateView):
    """Report to view all transactions excluding those involving user accounts."""

    template_name = "reports/transactions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "transactions": Transaction.objects.filter(
                    moment__year=self.get_year(),
                    source__user__isnull=True,
                    target__user__isnull=True,
                ).order_by("moment")
            }
        )
        return context


class CashFlowMatrixView(ReportAccessMixin, TemplateView):
    pass


class StaleAccountsView(ReportAccessMixin, TemplateView):
    pass


class DinerReportView(TemplateView):
    """Reports on diner counts."""

    pass
