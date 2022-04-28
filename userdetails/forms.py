from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from userdetails.models import User, Association, UserMembership


class CreateUserForm(UserCreationForm):
    # Note: associations field is required
    associations = forms.ModelMultipleChoiceField(queryset=Association.objects.filter(is_choosable=True),
                                                  widget=forms.CheckboxSelectMultiple())

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'email', 'first_name', 'last_name', 'dietary_requirements')
        field_classes = {'username': UsernameField}  # This adds some HTML attributes for semantics

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

    def save(self, commit=True):
        """Saves user and creates the memberships."""
        user = super().save(commit=False)
        if commit:
            with transaction.atomic():
                user.save()
                for association in self.cleaned_data['associations']:
                    UserMembership.objects.create(related_user=user, association=association)
        return user


class UserForm(forms.ModelForm):
    name = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ('username', 'name', 'email', 'dietary_requirements', 'email_public', 'phone_number')
        labels = {
            'email_public': 'E-mail visible'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].disabled = True
        self.fields['name'].initial = str(self.instance)
        self.fields['name'].help_text = "Contact the site administrator if you want to change your name."
        self.fields['email'].disabled = True
        self.fields['email'].required = False  # This hides the asterisks


class MembershipForm(forms.Form):
    """Form used in account settings for choosing associations.

    Uses a custom template for rendering verified/rejected/pending.
    """

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Get choosable associations and associations the user is already a member of
        #
        # Note: 'distinct' is necessary because otherwise there will be a large
        # number of duplicate associations returned, resulting in a slow page
        # load.
        associations = Association.objects.filter(
            Q(is_choosable=True) | Q(usermembership__related_user=user)).distinct().order_by('slug')

        # Create fields for each association
        for association in associations:
            membership = UserMembership.objects.filter(related_user=user, association=association).first()
            # Disable if membership exists and is frozen
            disabled = membership and membership.is_frozen()
            # Set checked if there is a membership and it's not rejected
            initial = membership and not membership.is_rejected()

            field = forms.BooleanField(required=False, label=association.name, disabled=disabled, initial=initial)
            field.membership = membership  # Used by the view to show verified/rejected/pending badges
            field.association = association
            self.fields[association.slug] = field

    def clean(self):
        cleaned_data = super().clean()
        # Check if user is assigned to at least one association
        if not any(cleaned_data.values()):
            # pass
            raise ValidationError("At least one association needs to be chosen.")
        return cleaned_data

    def save(self):
        """Saves the memberships."""
        if self.errors:
            raise ValueError("The form didn't validate.")
        for slug, chosen in self.cleaned_data.items():
            # Get existing membership (if any)
            membership = self.fields[slug].membership
            association = self.fields[slug].association
            # Selected but no membership exists, need to create it
            if chosen and not membership:
                UserMembership.objects.create(related_user=self.user, association=association)
            # If user was rejected, and a new request is entered, set as pending
            if chosen and membership and membership.is_rejected():
                membership.set_verified(state=None)
                membership.save()
            # Not selected but there is a (non-rejected) membership, need to delete it
            if not chosen and membership and not membership.is_rejected():
                membership.delete()


class AssociationSettingsForm(forms.ModelForm):
    class Meta:
        model = Association
        fields = ('balance_update_instructions', 'invoicing_method', 'invoicing_description')
        help_texts = {
            'invoicing_method': "Name of the invoicing method. Only applicable if association can invoice members."
                                " For instance 'Q-rekening' in the case of Quadrivium.",
        }
        widgets = {
            'invoicing_description': forms.TextInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.allow_invoicing:
            self.fields['invoicing_method'].disabled = True
            self.fields['invoicing_description'].disabled = True
        else:
            self.fields['invoicing_method'].required = True
            self.fields['invoicing_description'].required = True
