from django.db import models, transaction
from django.db.models import F, Sum
from django.utils import timezone
from UserDetails.models import User, Association
from CreditManagement.models import UserCredit
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from datetime import datetime, time
from decimal import Decimal
from django.conf import settings


class UserDiningSettings(models.Model):
    """
    Contains setting related to the dining lists and use of the dining lists.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
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
    """
    date = models.DateField(default=timezone.now)
    sign_up_deadline = models.DateTimeField(blank=True, null=True, help_text="Date/time before users need to sign up")
    serve_time = models.TimeField(default=time(18, 00))

    # Todo: implement name as url
    name = models.SlugField(blank=True, default="", null=True, db_index=False, max_length=30)
    dish = models.CharField(default="", max_length=30, blank=True, help_text="The dish made")
    # The days adjustable is implemented to prevent adjustment in credits or aid due to a deletion of a user account.
    days_adjustable = models.IntegerField(
        default=2,
        help_text="The amount of days after occurance that one can add/remove users etc")
    claimed_by = models.ForeignKey(User, blank=True, related_name="dininglist_claimer", null=True,
                                   on_delete=models.SET_NULL)
    association = models.ForeignKey(Association, blank=True, null=True, on_delete=models.CASCADE,
                                    unique_for_date="date")
    # Todo: implement limit in the views.
    limit_signups_to_association_only = models.BooleanField(
        default=False, help_text="Whether only members of the given association can sign up")
    # The person who paid can be someone else
    #  this is displayed in the dining list and this user can update payment status.
    purchaser = models.ForeignKey(User, related_name="dininglist_purchaser", blank=True, null=True,
                                  on_delete=models.SET_NULL)

    kitchen_cost = models.DecimalField(decimal_places=2, verbose_name="kitchen cost per person", max_digits=4,
                                       default=0.50, validators=[MinValueValidator(Decimal('0.00'))])
    dinner_cost_total = models.DecimalField(decimal_places=2, verbose_name="total dinner costs", max_digits=5,
                                            default=0, validators=[MinValueValidator(Decimal('0.00'))])
    dinner_cost_single = models.DecimalField(decimal_places=2, verbose_name="dinner cost per person", max_digits=5,
                                             blank=True, null=True, default=2,
                                             validators=[MinValueValidator(Decimal('0.00'))])
    dinner_cost_keep_single_constant = models.BooleanField(default=False, verbose_name="Define costs from single price")
    auto_pay = models.BooleanField(default=False)

    tikkie_link = models.CharField(blank=True, null=True, verbose_name="tikkie hyperlink", max_length=50)

    diners = models.IntegerField(default=0)
    min_diners = models.IntegerField(default=4)
    max_diners = models.IntegerField(default=20)

    objects = DiningListManager()

    def save(self, *args, **kwargs):
        """
        Overwrite the save function to lock changes after closure
        :param args:
        :param kwargs:
        :return: None
        """
        if self.isAdjustable() is True:
            try:
                previous_list = DiningList.objects.get(pk=self.pk)
            except ObjectDoesNotExist:
                previous_list = None

            # Set the sign-up deadline to it's default value if none was provided.
            if self.sign_up_deadline is None:
                from Dining.constants import DINING_LIST_CLOSURE_TIME
                loc_time = timezone.datetime.combine(self.date, DINING_LIST_CLOSURE_TIME)
                loc_time = timezone.get_default_timezone().localize(loc_time)
                self.sign_up_deadline = loc_time

            # Compute the individual dinner costs per person
            if not self.dinner_cost_keep_single_constant:
                if self.diner_count() == 0:
                    self.dinner_cost_single = 0.0
                else:
                    self.dinner_cost_single = self.dinner_cost_total / self.diner_count()

            # Change all the user states
            with transaction.atomic():
                super(DiningList, self).save(*args, **kwargs)
                self.refresh_from_db()
                if previous_list is not None:
                    costs = previous_list.get_credit_cost() - self.get_credit_cost()
                else:
                    costs = -self.get_credit_cost()

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
            return
        else:
            if self.sign_up_deadline is None:
                from Dining.constants import DINING_LIST_CLOSURE_TIME
                self.sign_up_deadline = datetime.combine(self.date, DINING_LIST_CLOSURE_TIME)
            super(DiningList, self).save(update_fields=['days_adjustable', 'name'], **kwargs)
            return

    def get_credit_cost(self):
        """
        Returns the total cost to be used for the credit system
        :return: The cost of the list
        """
        costs = self.kitchen_cost
        if self.auto_pay:
            if self.dinner_cost_single is not None:
                # If it was none, the amount of diners is 0 and the costs should not be computed
                costs += self.dinner_cost_single
        return costs

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

    def isAdjustable(self):
        """
        Whether the dining list has not expired it's adjustable date
        :return: Whether the list properties can be adjusted.
        """
        days_since_date = (timezone.now().date() - self.date).days
        return days_since_date <= self.days_adjustable

    def clean(self):
        """
        Confirms model validation
        :return: Whether it is a valid model
        """
        if self.auto_pay:
            if self.get_purchaser() is None:
                raise ValidationError({
                    'claimed_by': ValidationError(
                        'When autopay is enabled, either a claimer or a purchaser must be defined.', code='invalid'),
                    'purchaser': ValidationError(
                        'When autopay is enabled, either a claimer or a purchaser must be defined.', code='invalid'),
                })

    def get_entry_user(self, user_id):
        """
        Returns the entry for the given user id
        :param user_id: The id of the user
        :return: The diningEntry instance
        """
        try:
            return self.diningentry_set.get(user_id=user_id)
        except ObjectDoesNotExist:
            return None

    def get_entry(self, entry_id):
        """
        Returns the entry with the given id that is affiliated with this dining list
        """
        try:
            return self.diningentry_set.get(id=entry_id)
        except ObjectDoesNotExist:
            return None

    def get_entry_external(self, entry_id):
        """
        Returns the external entry instance that is affiliated with this dining list
        """
        try:
            return self.diningentryexternal_set.get(id=entry_id)
        except ObjectDoesNotExist:
            return None

    def is_open(self):
        """
        Whether normal users can sign in/out for the dining list (i.e. the deadline has not expired)
        """
        return datetime.now().timestamp() < self.sign_up_deadline.timestamp()

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
            if self.get_entry_user(user.id) is not None:
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
        if not self.is_open() or self.diner_count() >= self.max_diners:
            return False

        if self.limit_signups_to_association_only:
            if user.usermemberships_set.filter(association=self.association).count() == 0:
                return False
        return True

    def __str__(self):
        return "{date} - {assoc} by {claimer}".format(date=self.date,
                                                      assoc= self.association.associationdetails.shorthand,
                                                      claimer=self.claimed_by)

    # Todo: deprecated
    @staticmethod
    def get_lists_on_date(date):
        return DiningList.objects.filter(date=date)

    def get_absolute_url(self):
        from .views import reverse_day
        slug = self.association.associationdetails.shorthand
        return reverse_day('slot_details', self.date, kwargs={'identifier': slug})

    def diner_count(self):
        return self.diningentry_set.count() + self.diningentryexternal_set.count()


class DiningEntry(models.Model):
    """
    Represents an entry on a dining list
    """

    # Dining list value should never be changed
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE, related_name='diningentry_set')
    # User value should never be changed
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    added_by = models.ForeignKey(User, related_name="added_entry_on_dining", on_delete=models.SET_DEFAULT, blank=True,
                                 default=None, null=True)
    has_shopped = models.BooleanField(default=False)
    has_cooked = models.BooleanField(default=False)
    has_cleaned = models.BooleanField(default=False)
    has_paid = models.BooleanField(default=False)

    class Meta:
        # User should be unique for each dining list
        unique_together = ("dining_list", "user")

    def save(self, *args, **kwargs):
        """
        An enhanced save implementation to ensure effects trickle down to the user stats and dining list.
        """

        # If dining list can not be adjusted, limit saving only to the update of the has_paid field.
        if not self.dining_list.isAdjustable():
            if self.id:
                # Only has_payed changes can go through
                super(DiningEntry, self).save(update_fields=['has_paid'])
                return
            else:
                raise ValueError("Dining list is locked")

        if self.id:
            # There is an older version get it.
            original = DiningEntry.objects.get(pk=self.pk)

            # Do not allow change of user, instead create a new entry
            if self.user != original.user:
                raise ValueError("User of a dining entry can't be changed")
        else:
            # Instance is being created
            # Todo: a transaction needs to be done, possibly here or when the dining list gets locked
            pass
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Block when dining list is locked
        if not self.dining_list.isAdjustable():
            raise ValueError("Dining list is locked")
        # Todo: a revert transaction possibly (depending on how transactions will be implemented)
        super().delete(*args, **kwargs)

    def clean(self):
        """
        Additional validation check
        :return: whether model is valid
        """
        if not self.dining_list.isAdjustable():
            if self.has_paid:
                if not DiningEntry.objects.get(pk=self.pk).has_paid:
                    super(DiningEntry, self).clean()
                    return

            raise ValidationError({
                'dining_list': ValidationError('This dining list is already locked', code='invalid'),
            })
        super(DiningEntry, self).clean()

    def __str__(self):
        return str(self.user) + " " + str(self.dining_list.date)

    def EID(self):
        """
        External id as used in urls
        :return:
        """
        return str(self.id)


class DiningEntryExternal(models.Model):
    """
    Represents an external dining list entry

    Todo: has a lot of code duplication with DiningEntry, needs to be merged somehow
    """
    # Dining list value should never be changed
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE, related_name='diningentryexternal_set')
    name = models.CharField(max_length=40)
    # User value should never be changed
    user = models.ForeignKey(User, verbose_name="added by (has cost responsibility)", on_delete=models.CASCADE)
    has_paid = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """
        An enhanced save implementation to ensure effects trickle down to the user stats and dining list.
        """
        # If dining list is no longer adjustable, block the save for anything but the has_paid update
        if not self.dining_list.isAdjustable():
            if self.id:
                # Only has_payed changes can go through
                super().save(update_fields=['has_paid'])
                return
            else:
                raise ValueError("Dining list is locked")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Block when dining list is locked
        if not self.dining_list.isAdjustable():
            raise ValueError("Dining list is locked")
        super().delete(*args, **kwargs)

    def clean(self):
        if not self.dining_list.isAdjustable():
            if self.has_paid:
                if not DiningEntry.objects.get(pk=self.pk).has_paid:
                    return super(DiningEntryExternal, self).clean()

            raise ValidationError({
                'dining_list': ValidationError('This dining list is already locked', code='invalid'),
            })
        return super(DiningEntryExternal, self).clean()

    def __str__(self):
        return self.name + " " + str(self.dining_list.date)

    def EID(self):
        return "E" + str(self.id)


class DiningComment(models.Model):
    """
    Comments for the dining list
    """
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    poster = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    pinned_to_top = models.BooleanField(default=False)


class DiningCommentView(models.Model):
    """
    Tracks whether certain comments have been read, i.e. the last time the comments page was visited.
    """
    dining_list = models.ForeignKey(DiningList, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)


class DiningDayAnnouncements(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=15)
    text = models.CharField(max_length=240)
    slots_occupy = models.IntegerField(default=0, help_text="The amount of slots this occupies")

    def __str__(self):
        return self.title
