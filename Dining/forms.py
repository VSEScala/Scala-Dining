from django import forms
from django.conf import settings
from django.db.models import OuterRef, Exists
from django.db import transaction
from django.utils.translation import gettext as _
from django.core.exceptions import PermissionDenied
from django.forms import ValidationError

from UserDetails.models import Association, User
from .models import DiningList, DiningEntry, DiningEntryUser, DiningEntryExternal, DiningComment
from General.util import SelectWithDisabled

from functools import reduce
from decimal import Decimal, ROUND_UP
from django.utils import timezone
from django.core.validators import MinValueValidator


def _clean_form(form):
    """
    Cleans the given form by validating it and throwing ValidationError if it is not valid.
    """
    if not form.is_valid():
        validation_errors = []
        for field, errors in form.errors.items():
            validation_errors.extend(["{}: {}".format(field, error) for error in errors])
        raise ValidationError(validation_errors)


class ServeTimeCheckMixin:
    """
    Mixin with clean_serve_time which gives errors on the serve_time if it is not within the kitchen opening hours
    """
    def clean_serve_time(self):
        serve_time = self.cleaned_data['serve_time']
        if serve_time < settings.KITCHEN_USE_START_TIME:
            raise ValidationError(_("Kitchen can't be used this early"))
        if serve_time > settings.KITCHEN_USE_END_TIME:
            raise ValidationError(_("Kitchen can't be used this late"))

        return serve_time


class CreateSlotForm(ServeTimeCheckMixin, forms.ModelForm):
    class Meta:
        model = DiningList
        fields = ('dish', 'association', 'max_diners', 'serve_time')

    def __init__(self, user, date, *args, **kwargs):
        super(CreateSlotForm, self).__init__(*args, **kwargs)
        self.user = user
        self.date = date

        # Get associations that the user is a member of
        associations = Association.objects.filter(usermembership__related_user=user)

        # Filter out unavailable associations (those that have a dining list already on this day)
        dining_lists = DiningList.objects.filter(date=date, association=OuterRef('pk'))
        available = associations.annotate(occupied=Exists(dining_lists)).filter(occupied=False)
        unavailable = associations.annotate(occupied=Exists(dining_lists)).filter(occupied=True)

        if unavailable.exists():
            help_text = _(
                'Some of your associations are not available since they already have a dining list for this date.')
        else:
            help_text = ''

        widget = SelectWithDisabled(disabled_choices=[(a.pk, a.name) for a in unavailable])

        self.fields['association'] = forms.ModelChoiceField(queryset=available, widget=widget, help_text=help_text)

        if len(available) == 1:
            self.fields['association'].initial = available[0].pk
            self.fields['association'].disabled = True

    def clean(self):
        cleaned_data = super().clean()

        if DiningList.objects.available_slots(self.date) <= 0:
            raise ValidationError("All dining slots are already occupied on this day")

        # Check if user has enough money to claim a slot
        if self.user.usercredit.balance < settings.MINIMUM_BALANCE_FOR_DINING_SLOT_CLAIM:
            raise ValidationError("Your balance is too low to claim a slot")

        # Check if user has not already claimed another dining slot this day
        if DiningList.objects.filter(date=self.date, claimed_by=self.user).count() > 0:
            raise ValidationError(_("User has already claimed a dining slot this day"))

        # If date is valid
        if self.date < timezone.now().date():
            raise ValidationError("This date is in the past")
        if self.date == timezone.now().date() and timezone.now().time() > settings.DINING_SLOT_CLAIM_CLOSURE_TIME:
            raise ValidationError("It's too late to claim any dining slots")
        if self.date > timezone.now().date() + settings.DINING_SLOT_CLAIM_AHEAD:
            raise ValidationError("Dining list is too far in the future")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.claimed_by = self.user
        instance.date = self.date

        if commit:
            instance.save()
            DiningEntryUser(user=self.user, dining_list=instance).save()

        return instance


class DiningInfoForm(ServeTimeCheckMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        dining_list = kwargs.get("instance")
        super(DiningInfoForm, self).__init__(*args, **kwargs)

        query = dining_list.diners.distinct()
        self.fields['purchaser'].queryset = query

    class Meta:
        model = DiningList
        fields = ['serve_time', 'min_diners', 'max_diners', 'sign_up_deadline', 'purchaser']

    def save(self):
        self.instance.save(update_fields=self.Meta.fields)


class DiningPaymentForm(forms.ModelForm):
    dinner_cost_total = forms.DecimalField(decimal_places=2, max_digits=5, initial=Decimal(0.00),
                                           validators=[MinValueValidator(Decimal('0.00'))])

    class Meta:
        model = DiningList
        fields = ['dish', 'dinner_cost_total', 'dining_cost', 'payment_link']
        save_fields = ['dish', 'dining_cost', 'payment_link']
        help_texts = {
            'dinner_cost_total': 'Either adjust total dinner cost or single dinner cost',
            'dinner_cost_single': 'Either adjust total dinner cost or single dinner cost',
        }

    def __init__(self, *args, **kwargs):
        super(DiningPaymentForm, self).__init__(*args, **kwargs)

    def save(self):
        # If the single value has been added, recompute the total amount
        # also check if it has changed from earlier status
        old_list = DiningList.objects.get(id=self.instance.id)

        total_dinner_cost = self.cleaned_data['dinner_cost_total']

        if total_dinner_cost > 0:
            if self.instance.diners.count() > 0:
                s_cost = total_dinner_cost / self.instance.diners.count()
            else:
                s_cost = total_dinner_cost
            # round up slightly, to remove missing cents
            s_cost = Decimal(s_cost).quantize(Decimal('.01'), rounding=ROUND_UP)
            self.instance.dining_cost = s_cost

        self.instance.save(update_fields=DiningPaymentForm.Meta.save_fields)


class DiningEntryCreateForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=None)

    def __init__(self, added_by, dining_list, data=None, **kwargs):
        """
        The adder and dining_list parameters are used to find the users that can be used for this entry.
        """
        if data is not None:
            # User defaults to added_by if not set
            data = data.copy()
            data.setdefault('user', added_by.pk)
            data.setdefault('dining_list', dining_list.pk)

        super().__init__(**kwargs, data=data)

        # Find available users for this dining entry
        users = User.objects.all()

        self.fields['user'].queryset = users

    def clean_dining_list(self):
        # Clean the dining list relation
        dining_list = self.cleaned_data['dining_list']

        if not dining_list.can_add_diners(self.added_by):
            if dining_list.is_adjustable():
                # If it blocked, but the list is adjustable. The user has no special permissions
                if not dining_list.is_open():
                    raise ValidationError(_("Dining list is closed or can't be changed."), code='closed')
                elif not dining_list.has_room():
                    raise ValidationError(_("Dining list is full."), code='full')
                elif self.added_by.usermembership_set.filter(association=self.association).count() == 0:
                    # The list is open and has room, so it must be members only
                    raise ValidationError(_("Dining list is limited for members only."), code='members_only')
                else:
                    raise RuntimeError(_("Access blocked for undetermined reason"))
            else:
                # The user had authorisation, but the dining list is to old to be adjusted
                raise ValidationError(_("Dining list can no longer be adjusted."), code='closed')

        return dining_list


class DiningEntryUserCreateForm(DiningEntryCreateForm):

    class Meta:
        model = DiningEntryUser
        fields = ['dining_list', 'user']

    def __init__(self, added_by, dining_list, data=None, **kwargs):
        """
        The adder and dining_list parameters are used to find the users that can be used for this entry.
        """
        super().__init__(added_by, dining_list, data=data, **kwargs)

        # Set the added_by to the user who added it
        self.added_by = added_by
        self.instance.added_by = self.added_by

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        if (user.usercredit.balance < settings.MINIMUM_BALANCE_FOR_DINING_SIGN_UP and
                not reduce(lambda a,b: a or (user.is_member_of(b) and b.has_min_exception),
                    Association.objects.all(), False)):
            raise ValidationError("The balance of this user is too low to add", code='nomoneyzz')

        return cleaned_data


class DiningEntryExternalCreateForm(DiningEntryCreateForm):
    class Meta:
        model = DiningEntryExternal
        fields = ['name']

        self.fields['user'].queryset = self.fields['user'].queryset.filter(pk=adder.pk)
    def clean(self):
        cleaned_data = super().clean()
        user = self.instance.user
        if (user.usercredit.balance < settings.MINIMUM_BALANCE_FOR_DINING_SIGN_UP and
                not reduce(lambda a,b: a or (user.is_member_of(b) and b.has_min_exception),
                    Association.objects.all(), False)):
            raise ValidationError("Your balance is too low to add any external people", code='nomoneyzz')
        return cleaned_data


class DiningEntryDeleteForm(forms.ModelForm):
    class Meta:
        model = DiningEntry
        fields = []

    def __init__(self, deleted_by, instance, **kwargs):
        """
        Automatically binds on creation.
        """
        super().__init__(instance=instance, data={}, **kwargs)
        self.deleted_by = deleted_by

    def clean(self):
        cleaned_data = super().clean()

        dining_list = self.instance.dining_list

        # Dining list adjustable will have been checked in DiningList.clean()

        # Check permission
        if self.deleted_by != self.instance.user and not dining_list.is_authorised_user(self.deleted_by):
            raise ValidationError('Can only delete own entries')

        # Validate dining list is still open (except for claimant)
        if not dining_list.is_open():
            if not dining_list.is_authorised_user(self.deleted_by):
                raise ValidationError(_('The dining list is closed, ask the chef to remove this entry instead'),
                                      code='closed')
            elif not dining_list.is_adjustable():
                # If user is authorised, but dining list is no longer allowed to be adjusted
                raise ValidationError(_('The dining list is locked, changes can no longer be made'),
                                      code='locked')

        # (Optionally) block removal when the entry is the owner of the list
        # if self.instance.user == list.claimed_by:
        #     raise ValidationError(_("The claimant can't be removed from the dining list."), code='invalid')

        return cleaned_data

    def execute(self):
        # Try saving to check if form is validated (raises ValueError if not)
        self.save(commit=False)

        self.instance.delete()


class DiningListDeleteForm(forms.ModelForm):
    """
    Allows deletion of a dining list with it's entries. This will refund all kitchen costs.
    """
    class Meta:
        model = DiningList
        fields = []

    def __init__(self, deleted_by, instance, **kwargs):
        # Bind automatically on creation
        super().__init__(instance=instance, data={}, **kwargs)
        self.deleted_by = deleted_by
        # Create entry delete forms
        self.entry_delete_forms = [DiningEntryDeleteForm(deleted_by, entry) for entry in instance.dining_entries.all()]

    def clean(self):
        cleaned_data = super().clean()

        # Optionally check min/max diners here

        # Also validate all entry deletions
        for entry_deletion in self.entry_delete_forms:
            if not entry_deletion.is_valid():
                raise ValidationError(entry_deletion.non_field_errors())

        return cleaned_data

    def execute(self):
        """
        Deletes the dining list by first deleting the entries and after that deleting the dining list.
        """
        # Check if validated
        self.save(commit=False)

        with transaction.atomic():
            # Delete all entries (this will refund kitchen cost)
            for entry_deletion in self.entry_delete_forms:
                entry_deletion.execute()
            # Delete dining list
            self.instance.delete()

        # After database succeeded, send out a mail to all entries
        # mail()


class DiningCommentForm(forms.ModelForm):
    min_message_length = 3

    class Meta:
        model = DiningComment
        fields = ['message']

    def __init__(self, poster, dining_list, pinned=False, data=None, **kwargs):
        if data is not None:
            print(dining_list)
            # User defaults to added_by if not set
            data = data.copy()
            data.setdefault('poster', poster.pk)
            data.setdefault('dining_list', dining_list.pk)
            data.setdefault('pinned_to_top', pinned)

        super().__init__(**kwargs, data=data)

        self.dining_list = dining_list
        self.added_by = poster
        self.pinned = pinned

    def clean_message(self):
        cleaned_data = super().clean()
        message = cleaned_data.get('message')

        if len(message) < self.min_message_length:
            raise ValidationError(_("Comments need to be at least {} characters.").format(self.min_message_length))

        return message

    def save(self, *args, **kwargs):
        self.instance.poster = self.added_by
        self.instance.dining_list = self.dining_list
        self.instance.pinned_to_top = self.pinned
        print(self.instance.message)

        super(DiningCommentForm, self).save(*args, **kwargs)
