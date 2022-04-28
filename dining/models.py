from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError, MultipleObjectsReturned
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.formats import date_format

from creditmanagement.models import Transaction
from general.models import AbstractVisitTracker
from userdetails.models import User, Association


class DiningListManager(models.Manager):
    def available_slots(self, date):
        """Returns the number of available slots on the given date."""
        # Get slots occupied by announcements
        announce_slots = DiningDayAnnouncement.objects.filter(date=date).aggregate(Sum('slots_occupy'))
        announce_slots = 0 if announce_slots['slots_occupy__sum'] is None else announce_slots['slots_occupy__sum']
        return settings.MAX_SLOT_NUMBER - self.filter(date=date).count() - announce_slots


class DiningList(models.Model):
    """A single dining list (slot) model.

    The following fields may not be changed after creation: kitchen_cost!
    """
    date = models.DateField()

    """Todo: the date+association combination determines the URL. This makes it impossible to have multiple dining lists
    of the same association on the same day. Probably need to change that"""
    association = models.ForeignKey(Association, on_delete=models.PROTECT)
    owners = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='owned_dining_lists',
                                    help_text='Owners can manage the dining list.')

    sign_up_deadline = models.DateTimeField(help_text="The time before users need to sign up.")
    serve_time = models.TimeField(
        default=time(18, 00),
        validators=[MinValueValidator(settings.KITCHEN_USE_START_TIME, message="Kitchen can't be used this early."),
                    MaxValueValidator(settings.KITCHEN_USE_END_TIME, message="Kitchen can't be used this late.")])

    dish = models.CharField(default="", max_length=100, blank=True)
    # The days adjustable is implemented to prevent adjustment in credits or aid due to a deletion of a user account.
    adjustable_duration = models.DurationField(
        default=timedelta(days=2),
        help_text="How long a dining list can be adjusted after its date.")
    # Todo: implement limit in the views.
    limit_signups_to_association_only = models.BooleanField(
        default=False, help_text="Whether only members of the given association can sign up.")

    kitchen_cost = models.DecimalField(decimal_places=2, verbose_name="kitchen cost per person", max_digits=10,
                                       default=settings.KITCHEN_COST, validators=[MinValueValidator(Decimal('0.00'))])
    # Minimum value of 0 should be fine (minimum of 1 might be more intuitive but 0 makes it possible to close the list)
    max_diners = models.IntegerField(default=20, validators=[MinValueValidator(0)])
    diners = models.ManyToManyField(User, through='DiningEntry', through_fields=('dining_list', 'user'))

    objects = DiningListManager()

    def is_owner(self, user: User) -> bool:
        """Returns whether given user has all rights to this dining list.

        If we would like to give board members all rights to association dining
        lists, we could modify this method to implement that.
        """
        return self.owners.filter(pk=user.pk).exists()

    def is_expired(self):
        days_since_date = (self.date + self.adjustable_duration)
        return days_since_date < timezone.now().date()

    def is_adjustable(self):
        """Returns if the dining list is not expired."""
        return not self.is_expired()

    is_adjustable.boolean = True

    def clean(self):
        # Set sign up deadline if it hasn't been set already
        if not self.sign_up_deadline:
            loc_time = timezone.datetime.combine(self.date, settings.DINING_LIST_CLOSURE_TIME)
            loc_time = timezone.get_default_timezone().localize(loc_time)
            self.sign_up_deadline = loc_time

    def is_open(self):
        """Whether normal users can sign in/out for the dining list (i.e. the deadline has not expired)."""
        return timezone.now() < self.sign_up_deadline

    def has_room(self):
        """Determines whether this dining list can have more entries."""
        return self.diners.count() < self.max_diners

    def __str__(self):
        # Let's format date using SHORT_DATE_FORMAT so that it's consistent with other places
        return "{} {}".format(date_format(self.date, format="SHORT_DATE_FORMAT"), self.association)

    def get_absolute_url(self):
        from django.shortcuts import reverse
        return reverse('slot_details', kwargs={'pk': self.pk})

    def internal_dining_entries(self):
        """All dining entries that are not for external people."""
        return DiningEntry.objects.internal().filter(dining_list=self)

    def external_dining_entries(self):
        """All dining entries that are for external people."""
        return DiningEntry.objects.external().filter(dining_list=self)

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        # Valid sign up deadline
        if not exclude or 'sign_up_deadline' not in exclude:
            if self.sign_up_deadline and self.sign_up_deadline.date() > self.date:
                raise ValidationError(
                    {'sign_up_deadline': "Sign up deadline can't be later than the day dinner is served."})


class DiningEntryManager(models.Manager):
    def internal(self):
        return self.filter(external_name="")

    def external(self):
        return self.exclude(external_name="")


class DiningEntry(models.Model):
    """Represents an entry on a dining list."""

    dining_list = models.ForeignKey(DiningList, on_delete=models.PROTECT, related_name='entries')
    # This is the person who is responsible for the kitchen cost, it will be the same as the transaction source
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_dining_entries')
    # The kitchen transaction that belongs to this entry
    transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, null=True, blank=True)

    # If a name is provided, this entry is external
    external_name = models.CharField(max_length=100, blank=True)

    # Work/help stats
    has_shopped = models.BooleanField(default=False)
    has_cooked = models.BooleanField(default=False)
    has_cleaned = models.BooleanField(default=False)

    objects = DiningEntryManager()

    class Meta:
        verbose_name_plural = 'dining entries'

    def get_name(self):
        """Return name of diner."""
        return self.external_name or self.user.get_full_name()

    def is_internal(self):
        return not self.is_external()

    def is_external(self):
        return bool(self.external_name)

    def __str__(self):
        return "{}: {}".format(self.dining_list.date, self.get_name())

    def clean(self):
        if not self.pk:
            # Entry is being created, check if user is not already on the dining list
            if self.is_internal():
                if DiningEntry.objects.internal().filter(user=self.user, dining_list=self.dining_list).exists():
                    raise ValidationError("User is already on the dining list")


class DiningComment(models.Model):
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    poster = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=256)
    pinned_to_top = models.BooleanField(default=False)


class DiningCommentVisitTracker(AbstractVisitTracker):
    """Tracks whether certain comments have been read, i.e. the last time the comments page was visited."""
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE)

    @classmethod
    def get_latest_visit(cls, dining_list, user, update=False):
        """Gets the datetime of the latest visit.

        If there isn't one it either returns None, or the current time if update is set to True.

        Args:
            dining_list: The dining list the comment is part of.
            user: The user visiting the page.
            update: Update(?)
        """
        try:
            if update:
                latest_visit_obj, created = cls.objects.get_or_create(user=user, dining_list=dining_list)
            else:
                try:
                    latest_visit_obj = cls.objects.get(user=user, dining_list=dining_list)
                except cls.DoesNotExist:
                    return None
        except MultipleObjectsReturned:
            # A race condition occured and multiple were created. Clean up the entries
            visit_entries = cls.objects.filter(user=user, dining_list=dining_list)
            # Store 1 object, remove the others this could result in dataloss, but the problem is not noticeable
            latest_visit_obj = visit_entries.first()
            visit_entries.exclude(id=latest_visit_obj.id)
            visit_entries.delete()

        timestamp = latest_visit_obj.timestamp
        if update:
            latest_visit_obj.timestamp = timezone.now()
            latest_visit_obj.save()
        return timestamp

    def __str__(self):
        return "{dining_list} - {user}".format(dining_list=self.dining_list, user=self.user)


class DiningDayAnnouncement(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=100)
    text = models.TextField()
    slots_occupy = models.IntegerField(default=0, help_text="The amount of slots this occupies")

    def __str__(self):
        return self.title
