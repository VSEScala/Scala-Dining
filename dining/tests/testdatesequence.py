from datetime import date
from unittest import TestCase

from dining.datesequence import BaseSequencedDate, WeekdaySequencedDate


class DummySequencedDate(BaseSequencedDate):
    """Sequence which includes every even day, using ordinal."""

    @classmethod
    def upcoming(cls, from_date=None, reverse=False):
        ordinal = from_date.toordinal()
        if ordinal % 2 == 1:
            delta = 1 if not reverse else -1
            ordinal = ordinal + delta
        return DummySequencedDate.fromordinal(ordinal)


class BaseSequencedDateTestCase(TestCase):
    def test_next(self):
        ori = DummySequencedDate.fromordinal(4)
        expect = DummySequencedDate.fromordinal(6)
        actual = ori.next()
        self.assertEqual(expect, actual)

    def test_previous(self):
        ori = DummySequencedDate.fromordinal(4)
        expect = DummySequencedDate.fromordinal(2)
        actual = ori.previous()
        self.assertEqual(expect, actual)


class WeekdaySequencedDateTestCase(TestCase):
    def test_upcoming_weekend(self):
        # From a saturday
        actual1 = WeekdaySequencedDate.upcoming(date(2019, 4, 27))
        # From a sunday
        actual2 = WeekdaySequencedDate.upcoming(date(2019, 4, 28))
        expect = WeekdaySequencedDate(2019, 4, 29)
        self.assertEqual(expect, actual1)
        self.assertEqual(expect, actual2)

    def test_upcoming_weekday(self):
        # Friday
        actual = WeekdaySequencedDate.upcoming(date(2019, 4, 26))
        expect = WeekdaySequencedDate(2019, 4, 26)
        self.assertEqual(expect, actual)

    def test_upcoming_weekend_reverse(self):
        # From a saturday
        actual1 = WeekdaySequencedDate.upcoming(date(2019, 4, 27), reverse=True)
        # From a sunday
        actual2 = WeekdaySequencedDate.upcoming(date(2019, 4, 28), reverse=True)
        expect = WeekdaySequencedDate(2019, 4, 26)
        self.assertEqual(expect, actual1)
        self.assertEqual(expect, actual2)

    def test_upcoming_weekday_reverse(self):
        # Monday
        actual = WeekdaySequencedDate.upcoming(date(2019, 4, 29), reverse=True)
        expect = WeekdaySequencedDate(2019, 4, 29)
        self.assertEqual(expect, actual)
