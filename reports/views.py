from datetime import datetime
from decimal import Decimal
from itertools import pairwise

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import BadRequest
from django.utils.timezone import localdate, make_aware
from django.views.generic import TemplateView

from creditmanagement.models import Transaction, Account
from userdetails.models import Association


class ReportAccessMixin(UserPassesTestMixin):
    def test_func(self):
        # TODO rewrite to self.request.user.has_site_stats_access() when PR #276 is merged
        boards = Association.objects.filter(user=self.request.user)
        return True in (b.has_site_stats_access for b in boards)


class ReportsView(ReportAccessMixin, TemplateView):
    template_name = "reports/index.html"


class BalanceReportView(ReportAccessMixin, TemplateView):
    """Periodical reports of the balance of all credit accounts.

    User accounts are aggregated as one large pile. Association and bookkeeping
    accounts are shown individually.
    """

    template_name = "reports/balance.html"

    def get_year(self):
        try:
            return int(self.request.GET.get("year", localdate().year))
        except ValueError:
            raise BadRequest

    def period_boundaries(self):
        """Get periods.

        Period boundaries *must* be touching, i.e. start of next period is the
        same as the end of the current period.

        Yields:
            3-tuples with start of period, end of period, and display name.
        """
        return self.period_boundaries_quarterly()

    def period_boundaries_monthly(self):
        # Start of each period
        boundaries = [make_aware(datetime(self.get_year(), m, 1)) for m in range(1, 13)]
        # End of last period
        boundaries += [make_aware(datetime(self.get_year() + 1, 1, 1))]

        return ((a, b, a.strftime("%B")) for a, b in pairwise(boundaries))

    def period_boundaries_quarterly(self):
        year = self.get_year()

        def q(quartile):
            make_aware(datetime(year, (quartile - 1) * 3 + 1, 1))

        yield q(1), q(2), "Q1 January, February, March"
        yield q(2), q(3), "Q2 April, May, June"
        yield q(3), q(4), "Q3 July, August, September"
        yield q(4), make_aware(
            datetime(year + 1, 1, 1)
        ), "Q4 October, November, December"

    def get_report(self):
        """Computes the report values."""
        tx = Transaction.objects.all()

        boundaries = list(self.period_boundaries())

        # Compute opening balance
        running_balance = {
            account: increase - reduction
            for account, (increase, reduction) in tx.filter(moment__lt=boundaries[0][0])
            .sum_by_account(group_users=True)
            .items()
        }

        report = []
        for left, right, period_name in boundaries:
            # Compute credit and debit sum in the period
            mutation = tx.filter(moment__gte=left, moment__lt=right).sum_by_account(
                group_users=True
            )

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

            report.append((left, statements, period_name))
        return report

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # For the template: retrieve each Account instance, regroup by type and sort
        report = self.get_report()
        report_display = []
        account = {}  # Cache for Account lookups

        for period, statements, period_name in report:
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

            report_display.append(
                (period, bookkeeping, association, user_pile, period_name)
            )

        context.update(
            {
                "report_display": report_display,
                "year": self.get_year(),
            }
        )
        return context


class CashFlowReportView(TemplateView):
    """Periodical reports of money entering and leaving a specific account.

    For a selected account, shows the flow of money to and from other accounts
    in a certain period.
    """

    pass


class DinerReportView(TemplateView):
    """Reports on diner counts."""

    pass
