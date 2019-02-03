from django import forms
from django.contrib.auth import get_user_model
from django.db.models import OuterRef, Exists
from django.db import transaction
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError, PermissionDenied

from UserDetails.models import Association, User
from .models import DiningList, DiningEntry, DiningEntryUser
from General.util import SelectWithDisabled


def _clean_form(form):
    """
    Cleans the given form by validating it and throwing ValidationError if it is not valid.
    """
    if not form.is_valid():
        validation_errors = []
        for field, errors in form.errors.items():
            validation_errors.extend(["{}: {}".format(field, error) for error in errors])
        raise ValidationError(validation_errors)


class CreateSlotForm(forms.ModelForm):
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

        if unavailable:
            help_text = _(
                'Some of your associations are not available since they already have a dining list for this date.')
        else:
            help_text = ''

        widget = SelectWithDisabled(disabled_choices=[(a.pk, a.name) for a in unavailable])

        self.fields['association'] = forms.ModelChoiceField(queryset=available, widget=widget, help_text=help_text)

        if len(available) == 1:
            self.fields['association'].initial = available[0].pk
            self.fields['association'].disabled = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.claimed_by = self.user
        instance.date = self.date

        if commit:
            instance.save()

        return instance


class DiningInfoForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        dining_list = kwargs.get("instance")
        super(DiningInfoForm, self).__init__(*args, **kwargs)

        query = dining_list.diners
        self.fields['purchaser'].queryset = query

    class Meta:
        model = DiningList
        fields = ['serve_time', 'min_diners', 'max_diners', 'sign_up_deadline', 'purchaser']

    def save(self):
        self.instance.save(update_fields=self.Meta.fields)


class DiningPaymentForm(forms.ModelForm):
    class Meta:
        model = DiningList
        fields = ['dish', 'dinner_cost_total', 'dinner_cost_single', 'payment_link']
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

        if 0 < self.instance.dinner_cost_single != old_list.dinner_cost_single:
            self.instance.dinner_cost_total = self.instance.dinner_cost_single * self.instance.diners

        self.instance.save(update_fields=self.Meta.fields)


class DiningEntryCreateForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=None)

    class Meta():
        model = DiningEntryUser
        fields = ['dining_list', 'user']

    def __init__(self, adder, dining_list, data=None, **kwargs):
        """
        The adder and dining_list parameters are used to find the users that can be used for this entry.
        """
        if data is not None:
            # User defaults to adder if not set
            data = data.copy()
            data.setdefault('user', adder.pk)
            data.setdefault('dining_list', dining_list.pk)

        super().__init__(**kwargs, data=data)

        # Find available users for this dining entry
        users = User.objects.all()
        # First filter by association if the dining list is limited
        if dining_list.limit_signups_to_association_only:
            users.filter(usermembership__association=dining_list.association)
        # Filter by the adder if he is not the owner, since then he only may add himself, not others
        if adder != dining_list.claimed_by:
            users.filter(pk=adder.pk)
        self.fields['user'].queryset = users

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def save(self, commit=True):
        """
        Also creates a transaction when commit==True.
        """
        with transaction.atomic():
            # Possible race condition regarding instance validation
            instance = super().save(commit)
        return instance


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

        list = self.instance.dining_list

        # Dining list adjustable will have been checked in DiningList.clean()

        # Check permission
        if self.deleted_by != self.instance.user and self.deleted_by != list.claimed_by:
            raise PermissionDenied('Can only delete own entries.')

        # Validate dining list is still open (except for claimant)
        if not list.is_open():
            if self.deleted_by != list.claimed_by:
                raise ValidationError(_('The dining list is closed, ask the chef to remove this entry instead.'),
                                      code='closed')

        # (Optionally) block removal when the entry is the owner of the list
        # if self.instance.user == list.claimed_by:
        #     raise ValidationError(_("The claimant can't be removed from the dining list."), code='invalid')

        # Validate transaction
        _clean_form(self.transaction)

        return cleaned_data

    def execute(self):
        # Try saving to check if form is validated (raises ValueError if not)
        self.save(commit=False)

        with transaction.atomic():
            self.transaction.save()
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
