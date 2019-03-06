from django.db import models
from django.db.models import Sum

from django.conf import settings
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _

from datetime import datetime, timedelta, time
from decimal import Decimal
from UserDetails.models import User, Association
from General.models import AbstractVisitTracker


class UserDiningSettings(models.Model):
    """
    Contains setting related to the dining lists and use of the dining lists.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    allergies = models.CharField(max_length=100, blank=True, help_text="Leave empty if not applicable",
                                 verbose_name="Allergies or dietary restrictions")


class DiningListManager(models.Manager):
    def available_slots(self, date):
        """
        Returns the number of available slots on the given date.
        """
        # Get slots occupied by announcements
        announce_slots = DiningDayAnnouncements.objects.filter(date=date).aggregate(Sum('slots_occupy'))
        announce_slots = 0 if announce_slots['slots_occupy__sum'] is None else announce_slots['slots_occupy__sum']
        return settings.MAX_SLOT_NUMBER - len(self.filter(date=date)) - announce_slots


class DiningList(models.Model):
    """
    A single dining list (slot) model.

    The following fields may not be changed after creation: kitchen_cost, min_diners/max_diners!
    """
    date = models.DateField(default=timezone.now)
    sign_up_deadline = models.DateTimeField(help_text="The time before users need to sign up.")
    serve_time = models.TimeField(default=time(18, 00))

    dish = models.CharField(default="", max_length=30, blank=True, help_text="The dish made")
    # The days adjustable is implemented to prevent adjustment in credits or aid due to a deletion of a user account.
    adjustable_duration = models.DurationField(
        default=settings.TRANSACTION_PENDING_DURATION,
        help_text="The amount of time the dining list can be adjusted after its date")
    claimed_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, related_name="dininglist_claimer", null=True,
                                   on_delete=models.SET_NULL)
    # Association is needed for kitchen cost transactions and url calculation and is therefore required and may not be
    # changed.
    association = models.ForeignKey(Association, on_delete=models.CASCADE, unique_for_date="date")
    # Todo: implement limit in the views.
    limit_signups_to_association_only = models.BooleanField(
        default=False, help_text="Whether only members of the given association can sign up")
    # The person who paid can be someone else
    #  this is displayed in the dining list and this user can update payment status.
    purchaser = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="dininglist_purchaser", blank=True, null=True,
                                  on_delete=models.SET_NULL)

    # Kitchen cost may not be changed after creation
    kitchen_cost = models.DecimalField(decimal_places=2, verbose_name="kitchen cost per person", max_digits=10,
                                       default=settings.KITCHEN_COST, validators=[MinValueValidator(Decimal('0.00'))])

    dining_cost = models.DecimalField(decimal_places=2, verbose_name="dinner cost per person", max_digits=5,
                                             blank=True, null=True, default=0,
                                             validators=[MinValueValidator(Decimal('0.00'))])

    auto_pay = models.BooleanField(default=False)

    payment_link = models.CharField(blank=True, max_length=100, help_text=_('Link for payment, e.g. a Tikkie link.'))

    min_diners = models.IntegerField(default=4, validators=[MaxValueValidator(settings.MAX_SLOT_DINER_MINIMUM)])
    max_diners = models.IntegerField(default=20, validators=[MinValueValidator(settings.MIN_SLOT_DINER_MAXIMUM)])

    diners = models.ManyToManyField(settings.AUTH_USER_MODEL, through='DiningEntry',
                                    through_fields=('dining_list', 'user'))

    objects = DiningListManager()

    def save(self, *args, **kwargs):
        # Set the sign-up deadline to it's default value if none was provided.
        if not self.pk and not self.sign_up_deadline:
            loc_time = timezone.datetime.combine(self.date, settings.DINING_LIST_CLOSURE_TIME)
            loc_time = timezone.get_default_timezone().localize(loc_time)
            self.sign_up_deadline = loc_time

        # Safety check for kitchen cost
        if self.pk and self.kitchen_cost != DiningList.objects.get(pk=self.pk).kitchen_cost:
            raise ValueError("Kitchen cost can't be changed after creation.")

        super().save(*args, **kwargs)

    def get_purchaser(self):
        """
        Returns the user who purchased for the dining list
        :return: The purchaser
        """
        if self.purchaser is None:
            if self.claimed_by is None:
                return self.association
            else:
                return self.claimed_by
        else:
            return self.purchaser

    def is_adjustable(self):
        """
        Whether the dining list has not expired it's adjustable date and can therefore not be modified anymore
        """
        days_since_date = (self.date + self.adjustable_duration)
        return True# days_since_date >= timezone.now().date()

    def clean(self):
        # Validate dining list can be changed
        # This also blocks changes for dining entries!
        if self.pk and not self.is_adjustable():
            raise ValidationError(gettext('The dining list is not adjustable.'), code='not_adjustable')

        if self.sign_up_deadline is not None and self.sign_up_deadline.date() > self.date:
            raise ValidationError(
                {'sign_up_deadline': ["Sign up deadline can not be later than the day dinner is served",]})

        # Check if purchaser is present when using auto pay
        if self.auto_pay and not self.get_purchaser():
            raise ValidationError(
                {'purchaser': ValidationError('When autopay is enabled, a purchaser must be defined.', code='invalid')})

    def is_open(self):
        """
        Whether normal users can sign in/out for the dining list (i.e. the deadline has not expired)
        """
        return timezone.now() < self.sign_up_deadline

    def has_room(self):
        """
        Determines whether this dining list can have more entries
        :return: Whether this list can get more entries
        """
        return self.is_open() and self.diners.count() < self.max_diners

    def can_join(self, user, check_for_self=True):
        """
        Determines if a user can join a dining list by checking the status of the list and the status of
        other dining list subscriptions.
        check_for_self determines whether a full check for self should take place. Default=True
        :param check_for_self: whether this user should be double checked for entries on this or other lists
        :param user: The user intending to join
        :return: If the user can join the list
        """
        if check_for_self:
            # if user is already on list

            if self.internal_dining_entries().filter(user=user).count() > 0:
                return False
            # if user is signed up to other closed dinging lists
            if len(DiningEntry.objects.filter(dining_list__date=self.date,
                                              dining_list__sign_up_deadline__lte=datetime.now(),
                                              user=user)) > 0:
                return False

        # if user is owner, he can do anything he can set his mind to. Don't let his dreams be dreams!
        if user == self.claimed_by:
            return True

        # if dining list is closed
        if not self.has_room():
            return False

        if self.limit_signups_to_association_only:
            if user.usermembership_set.filter(association=self.association).count() == 0:
                return False
        return True

    def __str__(self):
        return "{} - {} by {}".format(self.date, self.association.slug, self.claimed_by)

    def get_absolute_url(self):
        from django.shortcuts import reverse
        slug = self.association.slug
        d = self.date
        return reverse('slot_details', kwargs={'year': d.year, 'month': d.month, 'day': d.day, 'identifier': slug})

    def internal_dining_entries(self):
        """All dining entries that are not for external people."""
        return DiningEntryUser.objects.filter(dining_list=self)

    def external_dining_entries(self):
        """All dining entries that are not for external people."""
        return DiningEntryExternal.objects.filter(dining_list=self)


class DiningEntry(models.Model):
    """
    Represents an entry on a dining list.

    Do not change dining_list, user and added_by after creation!
    """

    # Dining list value should never be changed
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE, related_name='dining_entries')
    # User value should never be changed, is responsible for the money required
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    has_paid = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        # If dining list can not be adjusted, limit saving only to the update of the has_paid field.
        if not self.dining_list.is_adjustable():
            if self.id:
                # Only has_payed changes can go through
                super(DiningEntry, self).save(update_fields=['has_paid'])
                return

        super().save(*args, **kwargs)

    def clean(self):
        """
        This actually has a race condition problem which makes it possible to create more entries than max_diners, and
        it is also possible to add yourself multiple times! This is however very hard to prevent, although we could use
        a mutex lock for the time between validation and saving.
        """
        if not self.pk:
            # Validate dining list open
            # REDACTED: blocks owners from adding entries
            # if not self.dining_list.is_open():
            #     raise ValidationError({
            #         'dining_list': ValidationError(_("Dining list is closed."), code='closed'),
            #     })

            # Validate room available in dining list
            if self.dining_list.dining_entries.count() >= self.dining_list.max_diners:
                raise ValidationError({
                    'dining_list': ValidationError(gettext("Dining list is full."), code='full'),
                })

            # Validate user is not already subscribed for the dining list
            if self.get_internal() and self.dining_list.internal_dining_entries().filter(user=self.user).exists():
                raise ValidationError(gettext('This user is already subscribed to the dining list.'))

            # (Optionally) validate if user is not already on another dining list
            # if DiningList.objects.filter(date=self.dining_list.date, dining_entries__user=self.user)

    def get_internal(self):
        try:
            return self.diningentryuser
        except ObjectDoesNotExist:
            return None

    def get_external(self):
        try:
            return self.diningentryexternal
        except ObjectDoesNotExist:
            return None

    def name(self):
        external = self.get_external()
        if external:
            return external.name
        else:
            return self.user


class DiningWork(models.Model):
    # Define the unique id name to prevent conflicts with DiningEntry
    w_id = models.AutoField(primary_key=True)

    # Add the stats
    has_shopped = models.BooleanField(default=False)
    has_cooked = models.BooleanField(default=False)
    has_cleaned = models.BooleanField(default=False)


class DiningEntryUser(DiningEntry, DiningWork):
    added_by = models.ForeignKey(User, related_name="added_entry_on_dining", on_delete=models.SET_DEFAULT, blank=True,
                                 default=None, null=True)

    def clean(self):
        super().clean()
        if not self.pk:
            if DiningEntryUser.objects.filter(dining_list=self.dining_list, user=self.user):
                raise ValidationError(_("User is already on this dining list."))

    def __str__(self):
        return "{}: {}".format(self.dining_list.date, self.user)


class DiningEntryExternal(DiningEntry):
    name = models.CharField(max_length=40)

    def __str__(self):
        return "{}: {}".format(self.dining_list, self.name)


class DiningComment(models.Model):
    """
    Comments for the dining list
    """
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    poster = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.CharField(max_length=256)
    pinned_to_top = models.BooleanField(default=False)


class DiningCommentVisitTracker(AbstractVisitTracker):
    """
    Tracks whether certain comments have been read, i.e. the last time the comments page was visited.
    """
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE)

    @classmethod
    def get_latest_visit(cls, dining_list, user, update=False):
        """
        Get the datetime of the latest visit.
        If there isn't one it either returns None, or the current time if update is set to True
        :param dining_list: The dining list the comment is part of
        :param user: The user visiting the page
        :param update:
        :return:
        """
        if update:
            latest_visit_obj = cls.objects.get_or_create(user=user, dining_list=dining_list)[0]
        else:
            try:
                latest_visit_obj = cls.objects.get(user=user, dining_list=dining_list)
            except cls.DoesNotExist:
                return None

        timestamp = latest_visit_obj.timestamp
        if update:
            latest_visit_obj.timestamp = timezone.now()
            latest_visit_obj.save()
        return timestamp


class DiningDayAnnouncements(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=15)
    text = models.CharField(max_length=240)
    slots_occupy = models.IntegerField(default=0, help_text="The amount of slots this occupies")

    def __str__(self):
        return self.title
