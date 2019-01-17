from datetime import datetime, time
from decimal import Decimal

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from UserDetails.models import Association


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
    days_adjustable = models.IntegerField(
        default=2,
        help_text="The amount of days after occurance that one can add/remove users etc")
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
                                       default=Decimal('0.50'), validators=[MinValueValidator(Decimal('0.00'))])
    dinner_cost_total = models.DecimalField(decimal_places=2, verbose_name="total dinner costs", max_digits=10,
                                            default=0, validators=[MinValueValidator(Decimal('0.00'))])
    dinner_cost_single = models.DecimalField(decimal_places=2, verbose_name="dinner cost per person", max_digits=5,
                                             blank=True, null=True, default=2,
                                             validators=[MinValueValidator(Decimal('0.00'))])
    dinner_cost_keep_single_constant = models.BooleanField(default=False, verbose_name="Define costs from single price")
    auto_pay = models.BooleanField(default=False)

    tikkie_link = models.CharField(blank=True, null=True, verbose_name="tikkie hyperlink", max_length=50)

    min_diners = models.IntegerField(default=4)
    max_diners = models.IntegerField(default=20)

    diners = models.ManyToManyField(settings.AUTH_USER_MODEL, through='DiningEntry',
                                    through_fields=('dining_list', 'user'))

    objects = DiningListManager()

    def save(self, *args, **kwargs):
        # Set the sign-up deadline to it's default value if none was provided.
        if not self.pk and not self.sign_up_deadline:
            from Dining.constants import DINING_LIST_CLOSURE_TIME
            loc_time = timezone.datetime.combine(self.date, DINING_LIST_CLOSURE_TIME)
            loc_time = timezone.get_default_timezone().localize(loc_time)
            self.sign_up_deadline = loc_time

        # Safety check for kitchen cost
        if self.pk and self.kitchen_cost != DiningList.objects.get(pk=self.pk).kitchen_cost:
            raise ValueError("Kitchen cost can't be changed after creation.")

        super().save(*args, **kwargs)

        """
        # Compute the individual dinner costs per person
        if not self.dinner_cost_keep_single_constant:
            if self.dining_entries.count() == 0:
                self.dinner_cost_single = 0.0
            else:
                self.dinner_cost_single = self.dinner_cost_total / self.dining_entries.count()

        # Change all the user states
        with transaction.atomic():
            super(DiningList, self).save(*args, **kwargs)
            self.refresh_from_db()
            if previous_list is not None:
                costs = previous_list.get_credit_cost() - self.get_credit_cost()
            else:
                costs = -self.get_credit_cost()

            # Todo: update user credits
            if costs != 0:
                # Costs have changed, alter all credits.
                # Done in for-loop instead of update to trigger custom save implementation (to track negatives)
                for diningEntry in self.diningentry_set.all():
                    diningEntry.user.usercredit.credit = F('credit') + costs
                    diningEntry.user.usercredit.save()
                # Adjust the credit scores for each external entry added.
                # For loop is required to ensure that entries added by the same user are processed correctly
                for ExternalDinerEntry in self.diningentryexternal_set.all():
                    ExternalDinerEntry.user.usercredit.credit = F('credit') + costs
                    ExternalDinerEntry.user.usercredit.save()

            if previous_list is None or \
                    previous_list.diners * self.diner_count() == 0 or \
                    previous_list.auto_pay != self.auto_pay or \
                    previous_list.get_purchaser() != self.get_purchaser() or \
                    previous_list.dinner_cost_total != self.dinner_cost_total:

                if previous_list is not None and previous_list.auto_pay and previous_list.diners > 0:
                    credit_instance = previous_list.get_purchaser().get_credit_containing_instance()
                    credit_instance.credit = F('credit') - previous_list.dinner_cost_total
                    credit_instance.save()

                if self.auto_pay and self.diner_count() > 0:
                    credit_instance = self.get_purchaser().get_credit_containing_instance()
                    credit_instance.credit = F('credit') + self.dinner_cost_total
                    credit_instance.save()
        """

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
        days_since_date = (timezone.now().date() - self.date).days
        return days_since_date <= self.days_adjustable

    def clean(self):
        # Validate dining list can be changed
        # This also blocks changes for dining entries!
        if self.pk and not self.is_adjustable():
            raise ValidationError(_('The dining list is not adjustable.'), code='not_adjustable')

        # Check if purchaser is present when using auto pay
        if self.auto_pay and not self.get_purchaser():
            raise ValidationError(
                {'purchaser': ValidationError('When autopay is enabled, a purchaser must be defined.', code='invalid')})

    def is_open(self):
        """
        Whether normal users can sign in/out for the dining list (i.e. the deadline has not expired)
        """
        return timezone.now() < self.sign_up_deadline

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
            # if user is signed up to other closed dinging lists
            if len(DiningEntry.objects.filter(dining_list__date=self.date,
                                              dining_list__sign_up_deadline__lte=datetime.now(),
                                              user=user)) > 0:
                return False

        # if user is owner, he can do anything he can set his mind to. Don't let his dreams be dreams!
        if user == self.claimed_by:
            return True

        # if dining list is closed
        if not self.is_open() or self.dining_entries.count() >= self.max_diners:
            return False

        if self.limit_signups_to_association_only:
            if user.usermembership_set.filter(association=self.association).count() == 0:
                return False
        return True

    def __str__(self):
        return "{date} - {assoc} by {claimer}".format(date=self.date,
                                                      assoc= self.association.associationdetails.shorthand,
                                                      claimer=self.claimed_by)

    def get_absolute_url(self):
        from django.shortcuts import reverse
        slug = self.association.associationdetails.shorthand
        d = self.date
        return reverse('slot_details', kwargs={'year': d.year, 'month': d.month, 'day': d.day, 'identifier': slug})

    def internal_dining_entries(self):
        """All dining entries that are not for external people."""
        return self.dining_entries.filter(external_name="")


class DiningEntry(models.Model):
    """
    Represents an entry on a dining list.

    Do not change dining_list, user and added_by after creation!
    """

    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE, related_name='dining_entries')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='dining_entries')
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="added_entry_on_dining",
                                 on_delete=models.SET_DEFAULT, blank=True, default=None, null=True)
    # When this is for someone external, put his name here (this also marks the entry as being external)
    external_name = models.CharField(max_length=100, default="", blank=True)
    # Stats
    has_shopped = models.BooleanField(default=False)
    has_cooked = models.BooleanField(default=False)
    has_cleaned = models.BooleanField(default=False)
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
            if not self.dining_list.is_open():
                raise ValidationError({
                    'dining_list': ValidationError(_("Dining list is closed."), code='closed'),
                })

            # Validate room available in dining list
            if self.dining_list.dining_entries.count() >= self.dining_list.max_diners:
                raise ValidationError({
                    'dining_list': ValidationError(_("Dining list is full."), code='full'),
                })

            # Validate user is not already subscribed for the dining list
            if not self.is_external() and self.dining_list.internal_dining_entries().filter(user=self.user).exists():
                raise ValidationError(_('This user is already subscribed to the dining list.'))

            # (Optionally) validate if user is not already on another dining list
            #if DiningList.objects.filter(date=self.dining_list.date, dining_entries__user=self.user)

    def __str__(self):
        return str(self.user) + " " + str(self.dining_list.date)

    def is_external(self):
        return bool(self.external_name)


class DiningComment(models.Model):
    """
    Comments for the dining list
    """
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    poster = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    pinned_to_top = models.BooleanField(default=False)


class DiningCommentView(models.Model):
    """
    Tracks whether certain comments have been read, i.e. the last time the comments page was visited.
    """
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)


class DiningDayAnnouncements(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=15)
    text = models.CharField(max_length=240)
    slots_occupy = models.IntegerField(default=0, help_text="The amount of slots this occupies")

    def __str__(self):
        return self.title
