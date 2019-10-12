from datetime import date, timedelta


class BaseSequencedDate(date):
    """A date that is in a sequence of dates and has next/previous methods to move.

    This base class is a sequence over all dates. To create different
    sequences, subclass this and override the upcoming method.
    """

    @classmethod
    def upcoming(cls, from_date=None, reverse=False):
        """Returns the closest date in the sequence after given date, or before given date if reverse is True.

        If given date is in the sequence, this date itself is returned! (But as a sequence subclass.)
        If from_date is None, current date is used.
        """
        if not from_date:
            # Might want to use django.utils.timezone if we're going global
            return cls.today()
        return cls(from_date.year, from_date.month, from_date.day)

    def next(self):
        return self.upcoming(self + timedelta(days=1))

    def previous(self):
        return self.upcoming(self - timedelta(days=1), reverse=True)

    @classmethod
    def in_sequence(cls, d):
        """Returns True if the given date is in the sequence of this class, False otherwise."""
        return cls.upcoming(d) == d

    @classmethod
    def fromdate(cls, d):
        """Creates an instance using any date instance.

        Raises:
            ValueError: When given date is not in the sequence.
        """
        if not cls.in_sequence(d):
            raise ValueError("Date is not in the sequence")
        return cls(d.year, d.month, d.day)


class WeekdaySequencedDate(BaseSequencedDate):
    """Sequence consisting of all weekdays."""

    @classmethod
    def upcoming(cls, from_date=None, reverse=False):
        d = from_date if from_date else super().upcoming()
        if d.weekday() >= 5:
            # If weekend, move...
            if not reverse:
                # to next Monday
                d = d + timedelta(days=7 - d.weekday())
            else:
                # to previous Friday
                d = d - timedelta(days=d.weekday() - 4)
        return super().upcoming(d)


# Date sequence class that is in use in the application. Can change this into a Django setting to have it
# deployment specific (could e.g. exclude summer holiday)
sequenced_date = WeekdaySequencedDate
