from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.timezone import now

from creditmanagement.models import Transaction
from general.models import AbstractVisitTracker
from userdetails.models import Association, User


class DiningListManager(models.Manager):
    def available_slots(self, date):
        """Returns the number of available slots on the given date."""
        # Get slots occupied by announcements
        announce_slots = DiningDayAnnouncement.objects.filter(date=date).aggregate(
            Sum("slots_occupy")
        )
        announce_slots = (
            0
            if announce_slots["slots_occupy__sum"] is None
            else announce_slots["slots_occupy__sum"]
        )
        return settings.MAX_SLOT_NUMBER - len(self.filter(date=date)) - announce_slots


class DiningList(models.Model):
    """A single dining list (slot) model.

    The following fields may not be changed after creation: kitchen_cost!
    """

    date = models.DateField()

    """Todo: the date+association combination determines the URL. This makes it impossible to have multiple dining lists
    of the same association on the same day. Probably need to change that"""
    association = models.ForeignKey(Association, on_delete=models.PROTECT)
    owners = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="owned_dining_lists",
        help_text="Owners can manage the dining list.",
    )

    sign_up_deadline = models.DateTimeField(
        help_text="The time before users need to sign up."
    )
    serve_time = models.TimeField(default=time(18, 00))

    dish = models.CharField(default="", max_length=100, blank=True)
    dish_kind = models.CharField(
        verbose_name="kind of dish",
        max_length=20,
        blank=True,
        choices=[
            ("", "Not specified"),
            ("meat", "🍗 With meat"),
            ("fish", "🐟 With fish"),
            ("vegetarian", "🥕 Vegetarian"),
            ("vegan", "🌿 Vegan"),
            ("meat_or_vegetarian", "Meat or vegetarian"),
            ("meat_or_vegan", "Meat or vegan"),
        ],
    )

    # The days adjustable is implemented to prevent adjustment in credits or aid due to a deletion of a user account.
    adjustable_duration = models.DurationField(
        default=settings.TRANSACTION_PENDING_DURATION,
        help_text="How long the dining list can be adjusted after its date.",
    )
    # Todo: implement limit in the views.
    limit_signups_to_association_only = models.BooleanField(
        "Association only",
        default=False,
        help_text="Whether only members of the given association can sign up.",
    )

    kitchen_cost = models.DecimalField(
        decimal_places=2,
        verbose_name="kitchen cost per person",
        max_digits=10,
        default=settings.KITCHEN_COST,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    dining_cost = models.DecimalField(
        decimal_places=2,
        verbose_name="dinner cost per person",
        max_digits=5,
        blank=True,
        null=True,
        default=None,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    auto_pay = models.BooleanField(default=False)

    # Why max_length=2000? -> https://stackoverflow.com/q/417142/2373688
    payment_link = models.URLField(
        blank=True, max_length=2000, help_text="Link for payment, e.g. a Tikkie link."
    )

    max_diners = models.IntegerField(
        default=20, validators=[MinValueValidator(settings.MIN_SLOT_DINER_MAXIMUM)]
    )

    diners = models.ManyToManyField(
        User, through="DiningEntry", through_fields=("dining_list", "user")
    )

    objects = DiningListManager()

    def is_owner(self, user: User) -> bool:
        """Returns whether given user has all rights to this dining list.

        If we would like to give board members all rights to association dining
        lists, we could modify this method to implement that.
        """
        return self.owners.filter(pk=user.pk).exists()

    def is_adjustable(self):
        """Whether the dining list has not expired and can still be modified."""
        days_since_date = self.date + self.adjustable_duration
        return days_since_date >= timezone.now().date()

    is_adjustable.boolean = True

    def clean(self):
        # Set sign up deadline to a default if it hasn't been set already.
        if not self.sign_up_deadline:
            self.sign_up_deadline = datetime.combine(
                date=self.date,
                time=settings.DINING_LIST_CLOSURE_TIME,
                tzinfo=timezone.get_default_timezone(),
            )

    def is_open(self):
        """Whether normal users can sign in/out for the dining list (i.e. the deadline has not expired)."""
        return timezone.now() < self.sign_up_deadline

    def has_room(self):
        """Determines whether this dining list can have more entries."""
        return self.diners.count() < self.max_diners

    def __str__(self):
        return "{} {}".format(self.date, self.association)

    def get_absolute_url(self):
        from django.shortcuts import reverse

        slug = self.association.slug
        d = self.date
        return reverse(
            "slot_details",
            kwargs={"year": d.year, "month": d.month, "day": d.day, "identifier": slug},
        )

    def internal_dining_entries(self):
        """All dining entries that are not for external people."""
        return DiningEntry.objects.internal().filter(dining_list=self)

    def external_dining_entries(self):
        """All dining entries that are not for external people."""
        return DiningEntry.objects.external().filter(dining_list=self)

    def clean_fields(self, exclude=None):
        super().clean_fields(exclude=exclude)
        # Validate sign up deadline.
        #
        # We can't put this in clean(), because then forms which put this field in the exclude list break.
        if not exclude or "sign_up_deadline" not in exclude:
            if self.sign_up_deadline and self.sign_up_deadline.date() > self.date:
                raise ValidationError(
                    {
                        "sign_up_deadline": [
                            "Sign up deadline can't be later than the day dinner is served."
                        ]
                    }
                )

    def recently_commented(self) -> bool:
        """Returns True if the last comment is posted less than 12h ago."""
        last = self.comments.order_by("-timestamp").first()
        return last and last.timestamp > now() - timedelta(hours=12)


class DiningEntryManager(models.Manager):
    def internal(self):
        return self.filter(external_name="")

    def external(self):
        return self.exclude(external_name="")


class DiningEntry(models.Model):
    """Represents an entry on a dining list."""

    dining_list = models.ForeignKey(
        DiningList, on_delete=models.PROTECT, related_name="dining_entries"
    )

    # This is the person who is responsible for the kitchen cost. It will be the same as the transaction source.
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_dining_entries"
    )

    # The transaction that belongs to this entry.
    transaction = models.OneToOneField(
        Transaction, on_delete=models.PROTECT, null=True, blank=True
    )

    # If a name is provided, this entry is external.
    external_name = models.CharField(max_length=100, blank=True)

    has_paid = models.BooleanField(default=False)

    # Work/help stats
    has_shopped = models.BooleanField(default=False)
    has_cooked = models.BooleanField(default=False)
    has_cleaned = models.BooleanField(default=False)

    objects = DiningEntryManager()

    class Meta:
        verbose_name_plural = "dining entries"

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
        # Check for duplicate internal entry, when this entry is being created (i.e. self.pk is not set).
        #
        # It might happen that self.user did not clean. In that case the attribute is not available.
        if not self.pk and self.is_internal() and hasattr(self, "user"):
            if (
                DiningEntry.objects.internal()
                .filter(user=self.user.pk, dining_list=self.dining_list)
                .exists()
            ):
                raise ValidationError(
                    "User is already on the dining list", code="user_already_present"
                )


class DiningComment(models.Model):
    dining_list = models.ForeignKey(
        DiningList, on_delete=models.CASCADE, related_name="comments"
    )
    timestamp = models.DateTimeField(default=timezone.now)
    poster = models.ForeignKey(User, on_delete=models.PROTECT, related_name="comments")
    message = models.TextField()
    pinned_to_top = models.BooleanField(default=False)
    email_sent = models.BooleanField(
        default=False,
        help_text="Whether an e-mail notification was sent for this comment.",
    )
    deleted = models.BooleanField(default=False)

    def can_delete(self, user) -> bool:
        """Returns True if the user is the owner or poster."""
        return self.poster == user or self.dining_list.is_owner(user)

    def can_pin(self, user) -> bool:
        """Returns True if the user is owner of the dining list."""
        return self.dining_list.is_owner(user)

    def mark_deleted(self):
        """Marks as deleted and saves."""
        self.pinned_to_top = False
        self.deleted = True
        self.save()


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
                latest_visit_obj, created = cls.objects.get_or_create(
                    user=user, dining_list=dining_list
                )
            else:
                try:
                    latest_visit_obj = cls.objects.get(
                        user=user, dining_list=dining_list
                    )
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
        return "{dining_list} - {user}".format(
            dining_list=self.dining_list, user=self.user
        )


class DiningDayAnnouncement(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=100)
    text = models.TextField()
    slots_occupy = models.IntegerField(
        default=0, help_text="The amount of slots this occupies"
    )

    def __str__(self):
        return self.title


class PaymentReminderLock(models.Model):
    """Database table to prevent multiple payment reminder emails.

    This table stores temporary data and can safely be removed or recreated.

    See SlotPaymentView.
    """

    # We use primary_key=True to prevent an unnecessary auto id column.
    dining_list = models.OneToOneField(
        DiningList, on_delete=models.CASCADE, primary_key=True
    )  # Key
    sent = models.DateTimeField(null=True)  # Value


class DeletedList(models.Model):
    """For audit purposes, keep a log of deleted dining lists."""

    deleted_by = models.ForeignKey(User, on_delete=models.PROTECT)
    date = models.DateTimeField("deletion date", default=timezone.now)
    reason = models.TextField()
    json_list = models.TextField("JSON dining list")
    json_diners = models.TextField("JSON dining entries")

    def __str__(self):
        return f"Deleted on {self.date.date()} by {self.deleted_by}"
