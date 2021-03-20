import warnings
from decimal import Decimal, ROUND_UP

from dal_select2.widgets import ModelSelect2, ModelSelect2Multiple
from django import forms
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import transaction
from django.db.models import OuterRef, Exists
from django.forms import ValidationError
from django.utils import timezone

from creditmanagement.models import Transaction, Account
from dining.models import DiningList, DiningEntryUser, DiningEntryExternal, DiningComment, DiningEntry
from general.forms import ConcurrenflictFormMixin
from general.util import SelectWithDisabled
from userdetails.models import Association, UserMembership, User


def _clean_form(form):
    """Cleans the given form by validating it and throwing ValidationError if it is not valid."""
    if not form.is_valid():
        validation_errors = []
        for field, errors in form.errors.items():
            validation_errors.extend(["{}: {}".format(field, error) for error in errors])
        raise ValidationError(validation_errors)


class ServeTimeCheckMixin:
    """Mixin which gives errors on the serve_time if it is not within the kitchen opening hours."""

    def clean_serve_time(self):
        serve_time = self.cleaned_data['serve_time']
        if serve_time < settings.KITCHEN_USE_START_TIME:
            raise ValidationError("Kitchen can't be used this early")
        if serve_time > settings.KITCHEN_USE_END_TIME:
            raise ValidationError("Kitchen can't be used this late")
        return serve_time


class CreateSlotForm(ServeTimeCheckMixin, forms.ModelForm):
    class Meta:
        model = DiningList
        fields = ('dish', 'association', 'max_diners', 'serve_time')

    def __init__(self, creator: User, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.creator = creator

        # Get associations that the user is a member of (not necessarily verified)
        associations = Association.objects.filter(usermembership__related_user=creator)
        denied_memberships = UserMembership.objects.filter(related_user=creator, is_verified=False,
                                                           verified_on__isnull=False)
        associations = associations.exclude(usermembership__in=denied_memberships)

        # Filter out unavailable associations (those that have a dining list already on this day)
        dining_lists = DiningList.objects.filter(date=self.instance.date, association=OuterRef('pk'))
        available = associations.annotate(occupied=Exists(dining_lists)).filter(occupied=False)
        unavailable = associations.annotate(occupied=Exists(dining_lists)).filter(occupied=True)

        if unavailable.exists():
            help_text = "Some of your associations are not available since they already have a dining list for this date."
        else:
            help_text = ""

        widget = SelectWithDisabled(disabled_choices=[(a.pk, a.name) for a in unavailable])

        self.fields['association'] = forms.ModelChoiceField(queryset=available, widget=widget, help_text=help_text)

        if len(available) == 1:
            self.initial['association'] = available[0].pk
            self.fields['association'].disabled = True

        if associations.count() == 0:
            # Ready an error message as the user is not a member of any of the associations and thus can not create a slot
            self.cleaned_data = {}
            self.add_error(None,
                           ValidationError(
                               "You are not a member of any association and thus can not claim a dining list"))

    def clean(self):
        # Note: uniqueness for date+association is implicitly enforced using the association form field
        cleaned_data = super().clean()

        creator = self.creator

        if DiningList.objects.available_slots(self.instance.date) <= 0:
            raise ValidationError("All dining slots are already occupied on this day")

        # Check if user has enough money to claim a slot
        min_balance_exception = creator.has_min_balance_exception()
        if not min_balance_exception and creator.account.get_balance() < settings.MINIMUM_BALANCE_FOR_DINING_SLOT_CLAIM:
            raise ValidationError("Your balance is too low to claim a slot")

        # Check if user does not already own another dining list this day
        if DiningList.objects.filter(date=self.instance.date, owners=creator).exists():
            raise ValidationError("User already owns a dining list on this day")

        # If date is valid
        if self.instance.date < timezone.now().date():
            raise ValidationError("This date is in the past")
        if self.instance.date == timezone.now().date() and timezone.now().time() > settings.DINING_SLOT_CLAIM_CLOSURE_TIME:
            raise ValidationError("It's too late to claim any dining slots")
        if self.instance.date > timezone.now().date() + settings.DINING_SLOT_CLAIM_AHEAD:
            raise ValidationError("Dining list is too far in the future")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            # Make creator owner
            instance.owners.add(self.creator)

            # Create dining entry for creator
            user = self.creator
            entry_form = DiningEntryUserCreateForm({'user': str(user.pk)},
                                                   instance=DiningEntryUser(created_by=user, dining_list=instance))
            if entry_form.is_valid():
                entry_form.save()
            else:
                warnings.warn("Couldn't create dining entry while creating dining list")
        return instance


class DiningInfoForm(ConcurrenflictFormMixin, ServeTimeCheckMixin, forms.ModelForm):
    class Meta:
        model = DiningList
        fields = ['owners', 'dish', 'serve_time', 'min_diners', 'max_diners', 'sign_up_deadline']
        widgets = {
            'owners': ModelSelect2Multiple(url='people_autocomplete', attrs={'data-minimum-input-length': '1'}),
        }


class DiningPaymentForm(ConcurrenflictFormMixin, forms.ModelForm):
    dinner_cost_total = forms.DecimalField(decimal_places=2, max_digits=5, required=False,
                                           validators=[MinValueValidator(Decimal('0'))],
                                           help_text='Only one of dinner cost total or dinner cost per person should '
                                                     'be provided')

    class Meta:
        model = DiningList
        fields = ['dinner_cost_total', 'dining_cost', 'payment_link']

    def clean(self):
        """This cleaning calculates the person dining cost from the total dining cost."""
        cleaned_data = super().clean()
        dinner_cost_total = cleaned_data.get('dinner_cost_total')
        dining_cost = cleaned_data.get('dining_cost')

        # Sanity check: do not allow both dinner cost total and dinner cost per person
        if dinner_cost_total and dining_cost:
            msg = "Please only provide either dinner cost total or dinner cost per person"
            self.add_error('dinner_cost_total', msg)
            self.add_error('dining_cost', msg)
        elif dinner_cost_total:
            # Total dinner cost provided: calculate dining cost per person and apply
            if self.instance.diners.count() > 0:
                cost = dinner_cost_total / self.instance.diners.count()
            else:
                raise ValidationError({
                    'dinner_cost_total': "Can't calculate dinner cost per person as there are no diners"})

            # Round up to remove missing cents
            cost = Decimal(cost).quantize(Decimal('.01'), rounding=ROUND_UP)
            cleaned_data.update({
                'dinner_cost_total': None,
                'dining_cost': cost,
            })
        return cleaned_data


class DiningEntryUserCreateForm(forms.ModelForm):
    class Meta:
        model = DiningEntryUser
        fields = ['user']
        widgets = {
            # User needs to type at least 1 character, could change it to 2
            'user': ModelSelect2(url='people_autocomplete', attrs={'data-minimum-input-length': '1'})
        }

    def get_user(self):
        """Returns the user responsible for the kitchen cost (not necessarily creator)."""
        user = self.cleaned_data.get('user')
        if not user:
            raise ValidationError("User not provided")
        return user

    def clean(self):
        cleaned_data = super().clean()

        dining_list = self.instance.dining_list
        user = self.get_user()
        creator = self.instance.created_by

        # Adjustable
        if not dining_list.is_adjustable():
            raise ValidationError("Dining list can no longer be adjusted", code='closed')

        # Closed (exception for owner)
        if not dining_list.is_owner(creator) and not dining_list.is_open():
            raise ValidationError("Dining list is closed", code='closed')

        # Full (exception for owner)
        if not dining_list.is_owner(creator) and not dining_list.has_room():
            raise ValidationError("Dining list is full", code='full')

        if dining_list.limit_signups_to_association_only:
            # User should be verified association member, except when the entry creator is owner
            if not dining_list.is_owner(creator) and not user.is_verified_member_of(dining_list.association):
                raise ValidationError("Dining list is limited to members only", code='members_only')

        # User balance check
        if not user.has_min_balance_exception() and user.account.get_balance() < settings.MINIMUM_BALANCE_FOR_DINING_SIGN_UP:
            raise ValidationError("The balance of the user is too low to add", code='nomoneyzz')

        return cleaned_data

    def save(self, commit=True):
        """Creates a kitchen cost transaction and saves the entry."""
        if commit:
            with transaction.atomic():
                instance = super().save(commit=False)  # type: DiningEntry
                amount = instance.dining_list.kitchen_cost
                # Skip transaction if dining list is free
                if amount != Decimal('0.00'):
                    tx = Transaction.objects.create(source=instance.user.account,
                                                    target=Account.objects.get(special='kitchen_cost'),
                                                    amount=amount,
                                                    description="Kitchen cost for {}".format(instance.dining_list),
                                                    created_by=instance.created_by)
                    instance.transaction = tx
                instance.save()
                return instance

        return super().save(commit)


class DiningEntryExternalCreateForm(DiningEntryUserCreateForm):
    class Meta:
        model = DiningEntryExternal
        fields = ['name']

    def get_user(self):
        return self.instance.user


class DiningEntryDeleteForm(forms.Form):
    def __init__(self, entry: DiningEntry, deleter: User, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry = entry
        self.deleter = deleter

    def clean(self):
        cleaned_data = super().clean()

        dining_list = self.entry.dining_list
        is_owner = dining_list.is_owner(self.deleter)

        if not dining_list.is_adjustable():
            raise ValidationError("The dining list is locked, changes can no longer be made", code='locked')

        # Validate dining list is still open (except for claimant)
        if not is_owner and not dining_list.is_open():
            raise ValidationError("The dining list is closed, ask the chef to remove this entry instead", code='closed')

        # Check permission: either she's owner, or the entry is about herself, or she created the entry
        if not is_owner and self.entry.user != self.deleter and self.entry.created_by != self.deleter:
            raise ValidationError('Can only delete own entries')

        return cleaned_data

    def execute(self):
        with transaction.atomic():
            tx = self.entry.transaction
            if tx:
                tx.cancel(self.deleter)
                tx.save()
            self.entry.delete()


class DiningListDeleteForm(forms.ModelForm):
    """Allows deletion of a dining list with it's entries.

    This will refund all kitchen costs.
    """

    class Meta:
        model = DiningList
        fields = []

    def __init__(self, deleted_by, instance, **kwargs):
        # Bind automatically on creation
        super().__init__(instance=instance, data={}, **kwargs)
        self.deleted_by = deleted_by
        # Create entry delete forms
        self.entry_delete_forms = [DiningEntryDeleteForm(entry, deleted_by, {}) for entry in
                                   instance.dining_entries.all()]

    def clean(self):
        cleaned_data = super().clean()

        # Optionally check min/max diners here

        # Also validate all entry deletions
        for entry_deletion in self.entry_delete_forms:
            if not entry_deletion.is_valid():
                raise ValidationError(entry_deletion.non_field_errors())

        return cleaned_data

    def execute(self):
        """Deletes the dining list by first deleting the entries and after that deleting the dining list."""
        # Check if validated
        self.save(commit=False)

        with transaction.atomic():
            # Delete all entries (this will refund kitchen cost)
            for entry_deletion in self.entry_delete_forms:
                entry_deletion.execute()
            # Delete dining list
            self.instance.delete()


class DiningCommentForm(forms.ModelForm):
    class Meta:
        model = DiningComment
        fields = ['message']

    def __init__(self, poster, dining_list, pinned=False, data=None, **kwargs):
        if data is not None:
            # User defaults to added_by if not set
            data = data.copy()
            data.setdefault('poster', poster.pk)
            data.setdefault('dining_list', dining_list.pk)
            data.setdefault('pinned_to_top', pinned)

        super().__init__(**kwargs, data=data)

        self.dining_list = dining_list
        self.added_by = poster
        self.pinned = pinned

    def save(self, *args, **kwargs):
        self.instance.poster = self.added_by
        self.instance.dining_list = self.dining_list
        self.instance.pinned_to_top = self.pinned

        super().save(*args, **kwargs)
