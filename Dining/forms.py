from django import forms
from django.db.models import OuterRef, Exists
from django.db import transaction
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError, PermissionDenied

from UserDetails.models import Association, User
from .models import DiningList, DiningEntry
from General.util import SelectWithDisabled
from CreditManagement.models import Transaction


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

        query = User.objects.filter(dining_entries__in=dining_list.dining_entries.all())
        self.fields['purchaser'].queryset = query

    class Meta:
        model = DiningList
        fields = ['serve_time', 'min_diners', 'max_diners', 'sign_up_deadline', 'purchaser']

    def save(self):
        self.instance.save(update_fields=self.Meta.fields)


class DiningPaymentForm(forms.ModelForm):
    class Meta:
        model = DiningList
        fields = ['dish', 'dinner_cost_total', 'dinner_cost_single', 'tikkie_link']

    def __init__(self, *args, **kwargs):
        super(DiningPaymentForm, self).__init__(*args, **kwargs)

    def save(self):
        print("Save function")
        print(self.instance.dish)
        print(self.instance.dinner_cost_total)
        # If the single value has been added, recompute the total amount
        # also check if it has changed from earlier status
        old_list = DiningList.objects.get(id=self.instance.id)

        if 0 < self.instance.dinner_cost_single != old_list.dinner_cost_single:
            self.instance.dinner_cost_total = self.instance.dinner_cost_single * self.instance.diners

        print(self.instance.dinner_cost_single)
        print(self.instance.dinner_cost_total)
        self.instance.save(update_fields=self.Meta.fields)


class DiningEntryForm(forms.ModelForm):
    class Meta:
        model = DiningEntry
        fields = ['has_shopped', 'has_cooked', 'has_cleaned', 'has_paid']


class DiningEntryCreateForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=None)

    class Meta(DiningEntryForm.Meta):
        model = DiningEntry
        fields = ['user', 'external_name']

    def __init__(self, adder, dining_list, data=None, **kwargs):
        if data is not None:
            # User defaults to adder if not set
            data = data.copy()
            data.setdefault('user', adder.pk)

        super().__init__(**kwargs, data=data, instance=DiningEntry(dining_list=dining_list, added_by=adder))

        # The dining list owner can add all users, other people can only add themselves
        if adder == dining_list.claimed_by:
            self.fields['user'].queryset = User.objects.all()
        else:
            self.fields['user'].queryset = User.objects.filter(pk=adder.pk)

    def save(self, commit=True):
        """
        Also creates a transaction when commit==True.
        """
        if commit:
            with transaction.atomic():
                # Possible race condition regarding instance validation
                instance = super().save(commit)
                Transaction.objects.create(amount=instance.dining_list.kitchen_cost,
                                           source_user=instance.user,
                                           target_association=instance.dining_list.association,
                                           notes=_('Kitchen cost'),
                                           dining_list=instance.dining_list)
        else:
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

        # Dining list adjustable should've been checked in DiningList.clean()

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

        return cleaned_data

    def execute(self):
        # Try saving to check if form is validated (raises ValueError if not)
        self.save(commit=False)

        with transaction.atomic():
            Transaction.objects.create(amount=self.instance.dining_list.kitchen_cost,
                                       source_association=self.instance.dining_list.association,
                                       target_user=self.instance.user,
                                       notes=_('Kitchen cost refund'),
                                       dining_list=self.instance.dining_list)
            self.instance.delete()
