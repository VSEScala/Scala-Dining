from decimal import Decimal

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import BadRequest
from django.db.models import Case, Q, Sum, When
from django.utils.timezone import localdate, now
from django.views.generic import DetailView, TemplateView

from creditmanagement.models import Account, Transaction
from reports.period import Period
from userdetails.models import Association, UserMembership


class ReportAccessMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.has_site_stats_access()


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
    """Mixin for yearly reporting periods.

    Attributes:
        view_choice: Boolean that enables or disables choosing a different view.
    """

    default_view = "yearly"
    view_choice = True

    def get_period(self) -> Period:
        view = self.request.GET.get("view", self.default_view)

        # When view_choice is False we can only use the default view
        if not self.view_choice and view != self.default_view:
            raise BadRequest

        try:
            period_class = Period.get_class(view)

            if "period" in self.request.GET:
                return period_class.from_url_param(self.request.GET["period"])
            else:
                return period_class.current()
        except ValueError:
            raise BadRequest

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["view_choice"] = self.view_choice
        if self.period:
            context["period"] = self.period
        return context

    def get(self, request, *args, **kwargs):
        # Add period to this instance
        self.period = self.get_period()
        return super().get(request, *args, **kwargs)


class BalanceView(ReportAccessMixin, PeriodMixin, TemplateView):
    """Periodical reports of the balance of all credit accounts.

    User accounts are aggregated as one large pile. Association and bookkeeping
    accounts are shown individually.
    """

    template_name = "reports/balance.html"

    def get_report(self):
        """Computes the balance statements."""
        if self.period.start() > now():
            # If the start of period is in the future, we cannot compute the start
            # balance and there are no statements.
            return {}

        # All transactions before current period
        before_tx = Transaction.objects.filter(moment__lt=self.period.start())
        # All transactions in this period
        period_tx = self.period.get_transactions()

        # Compute opening balance from all transaction before the current period
        opening = before_tx.sum_by_account(group_users=True)  # type: dict
        # Compute increase and reduction sum in this period
        mutation = period_tx.sum_by_account(group_users=True)  # type: dict

        # Add opening balances to report
        statements = {
            account: {"start_balance": increase - reduction}
            for account, (increase, reduction) in opening.items()
        }

        # Add mutations to report
        for account, (increase, reduction) in mutation.items():
            statement = statements.setdefault(account, {"start_balance": None})
            start = statement["start_balance"] or Decimal("0.00")
            statement.update(
                {
                    "increase": increase,
                    "reduction": reduction,
                    "end_balance": start + increase - reduction,
                }
            )

        return statements

    def get_context_data(self, **kwargs):
        # This function just regroups and sorts the values for display
        context = super().get_context_data(**kwargs)

        # The accounts to display in the report
        accounts = list(
            Account.objects.exclude(user__isnull=False).order_by(
                "special", "association__short_name"
            )
        )
        accounts.append(None)  # User pile

        # Add statements to context
        statements = self.get_report()
        context["rows"] = [
            (account, statements.get(getattr(account, "pk", None), {}))
            for account in accounts
        ]
        return context


class CashFlowView(ReportAccessMixin, PeriodMixin, DetailView):
    """Periodical reports of money entering and leaving a specific account.

    For a selected account, shows the flow of money to and from other accounts
    in a certain period.
    """

    template_name = "reports/cashflow.html"
    model = Account
    context_object_name = "account"

    def get_statements(self):
        """Returns a dictionary from Account or None to an income/outgoings tuple."""
        tx = self.period.get_transactions()
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Convert to list of tuples
        statements = [
            (account, inc, out) for account, (inc, out) in self.get_statements().items()
        ]
        # Sort in 3 steps to have first the bookkeeping accounts in
        # alphabetical order, then the association accounts in order and
        # then the user pile.
        #
        # This works because sort is stable.
        statements.sort(
            key=lambda v: v[0].association.name if v[0] and v[0].association else ""
        )
        statements.sort(key=lambda v: v[0].special if v[0] and v[0].special else "")
        statements.sort(
            key=lambda v: 2 if v[0] is None else 1 if v[0].association else 0
        )

        context["statements"] = statements
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
    default_view = "yearly"
    view_choice = False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "transactions": self.period.get_transactions()
                .filter(
                    source__user__isnull=True,
                    target__user__isnull=True,
                )
                .order_by("moment")
            }
        )
        return context


class CashFlowMatrixView(ReportAccessMixin, PeriodMixin, TemplateView):
    template_name = "reports/cashflow_matrix.html"

    def get_matrix(self):
        """Computes the cash flow matrix and returns a two-dimensional dictionary."""
        tx = self.period.get_transactions()

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
        accounts = list(
            Account.objects.filter(
                Q(association__isnull=False) | Q(special__isnull=False)
            ).order_by("special", "association__short_name")
        )
        # We add a `None` account indicating all user accounts
        accounts.append(None)

        # Format the matrices as 2D tables for display in the template
        matrix = self.get_matrix()
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
        context.update({"accounts": accounts, "table": table})
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


class DinerReportView(ReportAccessMixin, TemplateView):
    """Reports on diner counts."""

    pass


class MembershipCountView(ReportAccessMixin, TemplateView):
    """Simply shows the number of members per association."""

    template_name = "reports/memberships.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        mem = UserMembership.objects.all()
        report = [
            (
                association,
                # Pending memberships
                mem.filter(association=association, verified_on__isnull=True).count(),
                # Verified memberships
                mem.filter(association=association, is_verified=True).count(),
                # Declined memberships
                mem.filter(
                    association=association,
                    is_verified=False,
                    verified_on__isnull=False,
                ).count(),
            )
            for association in Association.objects.order_by("name")
        ]

        context.update({"report": report})
        return context
