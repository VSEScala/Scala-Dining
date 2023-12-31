# This is so over-engineered :')
from abc import ABC, abstractmethod
from datetime import datetime

from django.utils.timezone import localdate, make_aware

from creditmanagement.models import Transaction


class Period(ABC):
    """Abstract class for a reporting period.

    Attributes:
        view_name: Name of the period class used in the query string.
    """

    view_name = None

    @abstractmethod
    def start(self) -> datetime:
        """The aware datetime instance for the start of this period."""
        pass

    def end(self) -> datetime:
        """The aware datetime instance for the end of this period.

        Must be the same as the start of next period.
        """
        return self.next().start()

    @abstractmethod
    def display_name(self) -> str:
        pass

    @abstractmethod
    def next(self) -> "Period":
        """Returns the adjacent period directly after this one."""
        pass

    @abstractmethod
    def previous(self) -> "Period":
        """Returns the adjacent period directly before this one."""
        pass

    def get_transactions(self, tx=None):
        """Filter transactions in this period."""
        if tx is None:
            tx = Transaction.objects.all()
        return tx.filter(moment__gte=self.start(), moment__lt=self.end())

    def __str__(self):
        return self.display_name()

    @staticmethod
    def get_class(view_name: str):
        """Returns the period class for the given view name."""
        for cls in YearPeriod, QuarterPeriod, MonthPeriod:
            if cls.view_name == view_name:
                return cls
        raise ValueError

    @classmethod
    @abstractmethod
    def from_url_param(cls, period: str) -> "Period":
        """Returns the period instance from the string value.

        Raises:
            ValueError: When the parameter cannot be parsed.
        """
        pass

    @abstractmethod
    def url_param(self) -> str:
        """Get the string value of this instance for the URL parameter."""
        pass

    @abstractmethod
    def to_year(self) -> "YearPeriod":
        pass

    @abstractmethod
    def to_quarter(self) -> "QuarterPeriod":
        pass

    @abstractmethod
    def to_month(self) -> "MonthPeriod":
        pass

    @classmethod
    @abstractmethod
    def current(cls) -> "Period":
        """Returns the current period in local time."""
        pass


class MonthPeriod(Period):
    view_name = "monthly"

    def __init__(self, year: int, month: int):
        if month < 1 or month > 12:
            raise ValueError
        self.year = year
        self.month = month

    def start(self):
        return make_aware(datetime(self.year, self.month, 1))

    def display_name(self):
        return self.start().strftime("%B %Y")

    @classmethod
    def from_url_param(cls, period: str) -> "Period":
        int_val = int(period)
        return cls(int_val // 12, int_val % 12 + 1)

    def url_param(self) -> str:
        return str(self.year * 12 + self.month - 1)

    def next(self) -> "Period":
        return (
            MonthPeriod(self.year, self.month + 1)
            if self.month < 12
            else MonthPeriod(self.year + 1, 1)
        )

    def previous(self) -> "Period":
        return (
            MonthPeriod(self.year, self.month - 1)
            if self.month > 1
            else MonthPeriod(self.year - 1, 12)
        )

    def to_year(self) -> "YearPeriod":
        return YearPeriod(self.year)

    def to_quarter(self) -> "QuarterPeriod":
        return QuarterPeriod(self.year, (self.month - 1) // 3 + 1)

    def to_month(self) -> "MonthPeriod":
        return self

    @classmethod
    def current(cls) -> "Period":
        date = localdate()
        return MonthPeriod(date.year, date.month)


class QuarterPeriod(Period):
    view_name = "quarterly"

    def __init__(self, year: int, quarter: int):
        if quarter < 1 or quarter > 4:
            raise ValueError
        self.year = year
        self.quarter = quarter

    def start(self) -> datetime:
        return make_aware(datetime(self.year, (self.quarter - 1) * 3 + 1, 1))

    def display_name(self) -> str:
        return f"{self.year} Q{self.quarter}"

    def next(self) -> "Period":
        return (
            QuarterPeriod(self.year, self.quarter + 1)
            if self.quarter < 4
            else QuarterPeriod(self.year + 1, 1)
        )

    def previous(self) -> "Period":
        return (
            QuarterPeriod(self.year, self.quarter - 1)
            if self.quarter > 1
            else QuarterPeriod(self.year - 1, 4)
        )

    @classmethod
    def from_url_param(cls, period: str) -> "Period":
        int_val = int(period)
        return QuarterPeriod(int_val // 4, int_val % 4 + 1)

    def url_param(self) -> str:
        return str(self.year * 4 + self.quarter - 1)

    def to_year(self) -> "YearPeriod":
        return YearPeriod(self.year)

    def to_quarter(self) -> "QuarterPeriod":
        return self

    def to_month(self) -> "MonthPeriod":
        return MonthPeriod(self.year, (self.quarter - 1) * 3 + 1)

    @classmethod
    def current(cls) -> "Period":
        date = localdate()
        return QuarterPeriod(date.year, (date.month - 1) // 3 + 1)


class YearPeriod(Period):
    view_name = "yearly"

    def __init__(self, year: int):
        self.year = year

    def start(self) -> datetime:
        return make_aware(datetime(self.year, 1, 1))

    def display_name(self) -> str:
        return str(self.year)

    def next(self) -> "Period":
        return YearPeriod(self.year + 1)

    def previous(self) -> "Period":
        return YearPeriod(self.year - 1)

    @classmethod
    def from_url_param(cls, period: str) -> "Period":
        return YearPeriod(int(period))

    def url_param(self) -> str:
        return str(self.year)

    def to_year(self) -> "YearPeriod":
        return self

    def to_quarter(self) -> "QuarterPeriod":
        return QuarterPeriod(self.year, 1)

    def to_month(self) -> "MonthPeriod":
        return MonthPeriod(self.year, 1)

    @classmethod
    def current(cls) -> "Period":
        return YearPeriod(localdate().year)
