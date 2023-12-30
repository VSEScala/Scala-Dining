from datetime import datetime

from django.utils.timezone import make_aware

from creditmanagement.models import Transaction


class Period:
    def get_period_start(self) -> datetime:
        raise NotImplementedError

    def get_period_end(self) -> datetime:
        return self.next().get_period_start()

    def get_display_name(self) -> str:
        raise NotImplementedError

    def next(self) -> "Period":
        """Returns the adjacent period directly after this one."""
        raise NotImplementedError

    def get_transactions(self, tx=None):
        """Filter transactions in this period."""
        if tx is None:
            tx = Transaction.objects.all()
        return tx.filter(
            moment__gte=self.get_period_start(), moment__lt=self.get_period_end()
        )


class MonthPeriod(Period):
    def __init__(self, year: int, month: int):
        if month < 1 or month > 12:
            raise ValueError
        self.year = year
        self.month = month

    def get_period_start(self):
        return (make_aware(datetime(self.year, self.month, 1)),)

    def next(self) -> "Period":
        return (
            MonthPeriod(self.year, self.month + 1)
            if self.month < 12
            else MonthPeriod(self.year + 1, 1)
        )

    @classmethod
    def for_year(cls, year: int) -> list["MonthPeriod"]:
        return [cls(year, m) for m in range(1, 13)]

    def get_display_name(self):
        return self.get_period_start().strftime("%B")


class QuarterPeriod(Period):
    def __init__(self, year: int, quarter: int):
        if quarter < 1 or quarter > 4:
            raise ValueError
        self.year = year
        self.quarter = quarter

    def get_period_start(self) -> datetime:
        return make_aware(datetime(self.year, (self.quarter - 1) * 3 + 1, 1))

    def next(self) -> "Period":
        return (
            QuarterPeriod(self.year, self.quarter + 1)
            if self.quarter < 4
            else QuarterPeriod(self.year + 1, 1)
        )

    @classmethod
    def for_year(cls, year: int):
        return [cls(year, q) for q in range(1, 5)]

    def get_display_name(self) -> str:
        return (
            "Q1 January, February, March",
            "Q2 April, May, June",
            "Q3 July, August, September",
            "Q4 October, November, December",
        )[self.quarter - 1]
