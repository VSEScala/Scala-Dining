# This is so over-engineered :')
from abc import ABC, abstractmethod
from datetime import MAXYEAR, MINYEAR, datetime, timedelta

from django.utils.timezone import is_aware, localdate, make_aware, make_naive, now

from creditmanagement.models import Transaction
from dining.models import DiningList


class Period(ABC):
    """Abstract class for a reporting period.

    Attributes:
        view_name: Name of the period class used in the query string.
        view_display_name: Name shown on the buttons in the UI.
    """

    view_name = None
    view_display_name = None

    @staticmethod
    def get_view_classes():
        """Returns all different views."""
        return [
            AllTimePeriod,
            YearPeriod,
            QuarterPeriod,
            MonthPeriod,
            WeekPeriod,
            # DayPeriod,
            # SecondPeriod,
        ]

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
        """The period name of this instance, for example '2023 Q1'."""
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

    def get_dining_lists(self):
        """Returns a QuerySet for all dining lists in this period."""
        return DiningList.objects.filter(
            date__gte=localdate(self.start()),
            date__lt=localdate(self.end()),
        )

    def __str__(self):
        return self.display_name()

    @staticmethod
    def get_class(view_name: str):
        """Returns the period class for the given view name."""
        for cls in Period.get_view_classes():
            if cls.view_name == view_name:
                return cls
        raise ValueError

    def get_switcher(self) -> list["Period"]:
        """Returns a list of all the possible view classes for this period instance."""
        return [view.from_period(self) for view in Period.get_view_classes()]

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

    def is_current(self) -> bool:
        """Returns whether this is the current period."""
        return self.start() <= now() < self.end()

    @classmethod
    @abstractmethod
    def from_datetime(cls, d: datetime):
        """Returns the nearest period at this datetime."""
        pass

    @classmethod
    def from_period(cls, p: "Period"):
        """Converts a period instance to a different Period class."""
        if p.is_current():
            return cls.from_datetime(now())
        else:
            return cls.from_datetime(p.start())


class MonthPeriod(Period):
    view_name = "monthly"
    view_display_name = "Monthly"

    def __init__(self, year: int, month: int):
        if year < MINYEAR or year > MAXYEAR or month < 1 or month > 12:
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

    @classmethod
    def from_datetime(cls, d: datetime):
        d = localdate(d)
        return cls(d.year, d.month)


class QuarterPeriod(Period):
    view_name = "quarterly"
    view_display_name = "Quarterly"

    def __init__(self, year: int, quarter: int):
        if year < MINYEAR or year > MAXYEAR or quarter < 1 or quarter > 4:
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

    @classmethod
    def from_datetime(cls, d: datetime):
        return cls(d.year, (d.month - 1) // 3 + 1)


class YearPeriod(Period):
    view_name = "yearly"
    view_display_name = "Yearly"

    def __init__(self, year: int):
        if year < MINYEAR or year > MAXYEAR:
            raise ValueError
        self.year = year

    def start(self) -> datetime:
        return make_aware(datetime(self.year, 1, 1))

    def display_name(self) -> str:
        return str(self.year)

    def next(self) -> "Period":
        return YearPeriod(min(self.year + 1, MAXYEAR))

    def previous(self) -> "Period":
        return YearPeriod(max(self.year - 1, MINYEAR))

    @classmethod
    def from_url_param(cls, period: str) -> "Period":
        return YearPeriod(int(period))

    def url_param(self) -> str:
        return str(self.year)

    @classmethod
    def from_datetime(cls, d: datetime):
        return cls(localdate(d).year)


class AllTimePeriod(Period):
    view_name = "alltime"
    view_display_name = "All time"

    def start(self) -> datetime:
        return make_aware(datetime.min)

    def end(self) -> datetime:
        return make_aware(datetime.max)

    def display_name(self) -> str:
        return "All time"

    def next(self) -> "Period":
        return self

    def previous(self) -> "Period":
        return self

    @classmethod
    def from_url_param(cls, period: str) -> "Period":
        return cls()

    def url_param(self) -> str:
        return "all"

    @classmethod
    def from_datetime(cls, d: datetime):
        return cls()


class DateTimeBasePeriod(Period, ABC):
    """Period base implementation using naive datetime as period identifier."""

    def __init__(self, d: datetime):
        """Makes the date naive (if not already) and normalizes it."""
        if is_aware(d):
            d = make_naive(d)
        self.period_start = self.normalize(d)

    def start(self) -> datetime:
        return make_aware(self.period_start)

    @classmethod
    def from_url_param(cls, period: str) -> "Period":
        d = datetime.fromisoformat(period)
        if is_aware(d):
            raise ValueError
        return cls(d)

    def url_param(self) -> str:
        return self.period_start.isoformat()

    @classmethod
    def from_datetime(cls, d: datetime):
        return cls(d)

    @staticmethod
    @abstractmethod
    def normalize(d: datetime) -> datetime:
        """Gets the start of the period for the given date.

        The given date is assumed to be naive.
        """
        pass

    @abstractmethod
    def add(self, delta: int) -> "Period":
        """Gets the nth next or previous period."""
        pass

    def next(self) -> "Period":
        return self.add(1)

    def previous(self) -> "Period":
        return self.add(-1)


class WeekPeriod(DateTimeBasePeriod):
    view_name = "weekly"
    view_display_name = "Weekly"

    @staticmethod
    def normalize(d: datetime) -> datetime:
        # Zero out hour/minutes/seconds
        d = d.date()
        # To first day of the week
        d -= timedelta(days=d.weekday())
        return datetime(d.year, d.month, d.day)

    def add(self, delta: int) -> "Period":
        return WeekPeriod(self.period_start + delta * timedelta(days=7))

    def display_name(self) -> str:
        return (
            f"{self.period_start.year} week {self.period_start.isocalendar()[1]} "
            f"({self.period_start.day}-{self.period_start.month}-{self.period_start.year})"
        )


class DayPeriod(DateTimeBasePeriod):
    view_name = "daily"
    view_display_name = "Daily"

    @staticmethod
    def normalize(d: datetime) -> datetime:
        # Zero out hour/minutes/seconds
        d = d.date()
        return datetime(d.year, d.month, d.day)

    def add(self, delta: int) -> "Period":
        return DayPeriod(self.period_start + delta * timedelta(days=1))

    def display_name(self) -> str:
        return f"{self.period_start.day}-{self.period_start.month}-{self.period_start.year}"


class SecondPeriod(DateTimeBasePeriod):
    view_name = "seconds"
    view_display_name = "Per second"

    @staticmethod
    def normalize(d: datetime) -> datetime:
        return d.replace(microsecond=0)

    def add(self, delta: int) -> "Period":
        return SecondPeriod(self.period_start + delta * timedelta(seconds=1))

    def display_name(self) -> str:
        return self.period_start.isoformat()
