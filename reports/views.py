from decimal import Decimal

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import BadRequest
from django.db.models import Case, Sum, When, Q
from django.utils.timezone import localdate
from django.views.generic import DetailView, TemplateView

from creditmanagement.models import Account, Transaction
from reports.period import Period, QuarterPeriod, YearPeriod
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


class YearMixin:
    """Mixin for yearly reporting periods."""

    def get_year(self):
        try:
            return int(self.request.GET.get("year", localdate().year))
        except ValueError:
            raise BadRequest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["year"] = self.get_year()
        return context


class BalanceView(ReportAccessMixin, YearMixin, TemplateView):
    """Periodical reports of the balance of all credit accounts.

    User accounts are aggregated as one large pile. Association and bookkeeping
    accounts are shown individually.
    """

    template_name = "reports/balance.html"

    def get_report(self):
        """Computes the report values."""
        periods = QuarterPeriod.for_year(self.get_year())

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


class CashFlowView(ReportAccessMixin, YearMixin, DetailView):
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
        return regroup

    def get_report(self):
        periods = QuarterPeriod.for_year(self.get_year())
        return [(p, self.get_period_statement(p)) for p in periods]

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


class TransactionsReportView(ReportAccessMixin, YearMixin, TemplateView):
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


class CashFlowMatrixView(ReportAccessMixin, YearMixin, TemplateView):
    template_name = "reports/cashflow_matrix.html"

    def get_matrix(self, period):
        """Computes the cash flow matrix and returns a two-dimensional dictionary."""
        tx = period.get_transactions()

        # Group by source/target combinations and sum the amount
        qs = (
            # Set the group key to NULL for all user accounts
            tx.annotate(
                source_key=Case(
                    When(source__user__isnull=False, then=None),
                    default="source",
                ),
                target_key=Case(
                    When(target__user__isnull=False, then=None),
                    default="target",
                ),
            )
            .values("source_key", "target_key")
            .annotate(sum=Sum("amount"))
        )

        # Convert to 2D matrix
        matrix = {}
        for cell in qs:
            source = cell["source_key"]
            target = cell["target_key"]
            # Fetch Account from database
            if source:
                source = Account.objects.get(pk=source)
            if target:
                target = Account.objects.get(pk=target)

            # Enter in matrix
            matrix.setdefault(source, {})[target] = cell["sum"]

        return matrix

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Accounts to display in the matrix
        # TODO: change slug to short_name after #278 is merged
        accounts = list(
            Account.objects.filter(
                Q(association__isnull=False) | Q(special__isnull=False)
            ).order_by("special", "association__slug")
        )
        # We add a `None` account indicating all user accounts
        accounts.append(None)

        # Format the matrices as 2D tables for display in the template
        tables = []
        for period in [YearPeriod(self.get_year())]:
            matrix = self.get_matrix(period)
            table = [
                (
                    account_from,
                    [
                        (account_to, matrix.get(account_from, {}).get(account_to))
                        for account_to in accounts
                    ],
                )
                for account_from in accounts
            ]
            tables.append((period, table))

        context.update(
            {
                "accounts": accounts,
                "tables": tables,
            }
        )

        return context


class StaleAccountsView(ReportAccessMixin, TemplateView):
    """Report on the sum of account balances grouped in a period."""

    template_name = "reports/stale.html"

    def get_report(self) -> dict[str, dict]:
        # tx = Transaction.objects.filter()
        # Get balance and latest transaction date for all accounts
        data = Transaction.objects.sum_by_account(latest=True)

        # Exclude all non-user accounts (i.e. association and bookkeeping accounts)
        exclude = set(a.pk for a in Account.objects.exclude(user__isnull=False))

        # Group by quartile and aggregate
        report = {}
        for pk, (increase, reduction, last_date) in data.items():
            if pk in exclude:
                continue

            # If we omit localdate the timezone would be UTC and items might end up in
            # a different bucket.
            date = localdate(last_date)
            bucket = f"{date.year} Q{(date.month - 1) // 3 + 1}"
            balance = increase - reduction

            if balance and bucket not in report:
                report[bucket] = {
                    "positive_count": 0,
                    "positive_sum": Decimal("0.00"),
                    "negative_count": 0,
                    "negative_sum": Decimal("0.00"),
                }

            # Update count and sum
            if balance > 0:
                report[bucket]["positive_count"] += 1
                report[bucket]["positive_sum"] += balance
            elif balance < 0:
                report[bucket]["negative_count"] += 1
                report[bucket]["negative_sum"] += balance

        # Add totals
        for counts in report.values():
            counts["total_count"] = counts["positive_count"] + counts["negative_count"]
            counts["total_sum"] = counts["positive_sum"] + counts["negative_sum"]

        return report

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Format report as a list and sort
        report_display = [(q, counts) for q, counts in self.get_report().items()]
        report_display.sort(reverse=True)

        context.update({"report_display": report_display})
        return context


class DinerReportView(TemplateView):
    """Reports on diner counts."""

    pass
