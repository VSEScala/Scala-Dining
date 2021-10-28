import warnings
from decimal import Decimal

from dal_select2.widgets import ModelSelect2, ModelSelect2Multiple
from django import forms
from django.conf import settings
from django.db import transaction
from django.db.models import OuterRef, Exists
from django.forms import ValidationError
from django.utils import timezone

from creditmanagement.models import Transaction, Account
from dining.models import DiningList, DiningComment, DiningEntry
from general.util import SelectWithDisabled
from userdetails.models import Association, UserMembership, User


class CreateSlotForm(forms.ModelForm):
    # SIGN_UP_DEADLINE_CHOICES = (
    #     ('', 'Keep open until I manually close'),
    #     ('15:00', '15:00'),
    #     ('15:30', '15:30'),
    #     ('16:00', '16:00'),
    #     ('16:30', '16:30'),
    #     ('17:00', '17:00'),
    #     ('17:30', '17:30'),
    # )
    # sign_up_deadline = forms.TypedChoiceField(coerce=time,
    #                                           choices=SIGN_UP_DEADLINE_CHOICES,
    #                                           help_text="You can always change this later.",
    #                                           initial='15:30')

    class Meta:
        model = DiningList
        fields = ('dish', 'association', 'max_diners', 'serve_time')
        widgets = {
            'serve_time': forms.TimeInput(format='%H:%M'),
        }

    def __init__(self, creator: User, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.creator = creator

        # Get associations that the user is a member of (not necessarily verified)
        associations = Association.objects.filter(usermembership__related_user=creator)
        denied_memberships = UserMembership.objects.filter(related_user=creator, is_verified=False,
                                                           verified_on__isnull=False)
        associations = associations.exclude(usermembership__in=denied_memberships)

        # Filter out unavailable associations (those that have a dining list already on this day)
        dining_lists = DiningList.active.filter(date=self.instance.date, association=OuterRef('pk'))
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

        if DiningList.active.available_slots(self.instance.date) <= 0:
            raise ValidationError("All dining slots are already occupied on this day")

        # Check if user has enough money to claim a slot
        if creator.account.get_balance() < settings.MINIMUM_BALANCE_FOR_DINING_SLOT_CLAIM:
            raise ValidationError("Your balance is too low to claim a slot")

        # Check if user does not already own another dining list this day
        if DiningList.active.filter(date=self.instance.date, owners=creator).exists():
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
        instance = super().save(commit=False)  # type: DiningList
        # TODO: set sign up deadline

        if commit:
            instance.save()
            # Make creator owner
            instance.owners.add(self.creator)

            # Create dining entry for creator.
            #
            # This needs to be executed using the form to make sure that the
            # kitchen cost transaction is created as well.
            user = self.creator
            entry_form = DiningEntryInternalCreateForm({'user': str(user.pk)},
                                                       instance=DiningEntry(created_by=user, dining_list=instance))
            if entry_form.is_valid():
                entry_form.save()
            else:
                # Signing up might fail if there is a balance issue but that only occurs when
                # MINIMUM_BALANCE_FOR_DINING_SIGN_UP and MINIMUM_BALANCE_FOR_DINING_SLOT_CLAIM
                # are not equal.
                warnings.warn("Couldn't create dining entry while creating dining list")
        return instance


class DiningInfoForm(forms.ModelForm):
    class Meta:
        model = DiningList
        fields = ('owners', 'dish', 'serve_time', 'max_diners', 'sign_up_deadline')
        widgets = {
            'owners': ModelSelect2Multiple(url='people_autocomplete', attrs={'data-minimum-input-length': '1'}),
            'serve_time': forms.TimeInput(format='%H:%M'),
            'sign_up_deadline': forms.DateTimeInput(format='%d-%m-%Y %H:%M')
        }


class DiningEntryInternalCreateForm(forms.ModelForm):
    class Meta:
        model = DiningEntry
        fields = ('user',)
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
        if user.account.get_balance() < settings.MINIMUM_BALANCE_FOR_DINING_SIGN_UP:
            raise ValidationError("The balance of the user is too low to add", code='nomoneyzz')

        return cleaned_data

    def save(self, commit=True):
        """Creates a kitchen cost transaction and saves the entry."""
        instance = super().save(commit=False)  # type: DiningEntry
        if commit:
            with transaction.atomic():
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


class DiningEntryExternalCreateForm(DiningEntryInternalCreateForm):
    """Form for adding an external dining list entry.

    This works the same way as for an internal entry, except the external_name
    field is used in the form instead of the user field.
    """

    class Meta:
        model = DiningEntry
        fields = ('external_name',)
        labels = {'external_name': 'Name'}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fields['external_name'].required = True

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


class DiningListCancelForm(forms.ModelForm):
    """Cancels a dining list and refunds kitchen costs.

    Note that grocery payments will not be refunded by this form (at the moment).
    """

    class Meta:
        model = DiningList
        fields = ('cancelled_reason',)
        labels = {'cancelled_reason': 'Reason', }

    def __init__(self, cancelled_by, **kwargs):
        super().__init__(**kwargs)
        self.cancelled_by = cancelled_by
        self.fields['cancelled_reason'].required = True

    def save(self, commit=True):
        dining_list = super().save(commit=False)
        if commit:
            with transaction.atomic():
                # Refund transactions
                txs = Transaction.objects.filter(diningentry__dining_list=dining_list)
                for tx in txs:
                    tx.cancel(self.cancelled_by)
                    tx.save()
                dining_list.save()

        return dining_list


class DiningCommentForm(forms.ModelForm):
    class Meta:
        model = DiningComment
        fields = ('message',)

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
