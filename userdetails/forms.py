from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.core.exceptions import ValidationError
from django.utils import timezone

from userdetails.models import User, Association, UserMembership


class CreateUserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'email', 'first_name', 'last_name', 'dietary_requirements')
        field_classes = {'username': UsernameField}  # This adds some HTML attributes for semantics

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True


class UserForm(forms.ModelForm):
    name = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ('username', 'name', 'email', 'dietary_requirements', 'allow_grocery_payments', 'email_public',
                  'phone_number')
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


class AssociationLinkField(forms.BooleanField):
    """A special BooleanField model for association links.

    Can also indicate current validation state and auto-sets initial value.
    """

    def __init__(self, user: User, association: Association, *args, **kwargs):
        super().__init__(*args, initial=False, required=False, label=association.name, **kwargs)

        self.user = user
        self.association = association
        self.membership = None

        # Find the membership, if any
        if user:
            try:
                self.membership = association.usermembership_set.get(related_user=user)
                self.initial = self.membership.is_member()
                if self.membership.get_verified_state() is None:
                    self.pending = True

                # Check how recently the member has been verified or not. If too recent, block change
                if self.membership.verified_on is not None:
                    if self.membership.is_verified:
                        if self.membership.verified_on + \
                                settings.DURATION_AFTER_MEMBERSHIP_CONFIRMATION > timezone.now():
                            # The user has been verified to recently (prevent spamming)
                            self.disabled = True
                    else:
                        if self.membership.verified_on + \
                                settings.DURATION_AFTER_MEMBERSHIP_REJECTION > timezone.now():
                            # The user has been verified not to be a member to recently (prevent spamming)
                            self.disabled = True
            except UserMembership.DoesNotExist:
                pass

    def verified(self):
        if self.membership is None:
            return None
        return self.membership.get_verified_state()

    def get_membership_model(self, user=None, new_value=True):
        # Check input data for correctness
        if self.user is None and user is None:
            raise ValueError("Field does not contain user and user was not given in method")
        if user is not None and self.user is not None and self.user != user:
            raise ValueError("Given user differs from field user")

        if self.membership is not None:
            return self.membership
        if self.user is not None:
            # If there was a user given, but the link was not found. Create a new link if allowed
            if new_value:
                return UserMembership(related_user=self.user, association=self.association)
        else:
            # user originally not given. Try to find the link
            try:
                return self.association.usermembership_set.get(related_user=user)
            except UserMembership.DoesNotExist:
                if new_value:
                    return UserMembership(related_user=user, association=self.association)
        return None


class AssociationLinkForm(forms.Form):

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.user = user

        associations = Association.objects.filter(is_choosable=True)
        if user:
            # Adds non choosable associations the user is a member of
            associations |= Association.objects.filter(usermembership__related_user=user)
        associations = associations.order_by('slug')

        # Get all associations and make a checkbox field
        for association in associations:
            field = AssociationLinkField(user, association)
            # (using the slug since HTML IDs may not contain spaces)
            self.fields[association.slug] = field

    def clean(self):
        cleaned_data = super().clean()
        # Check if user is assigned to at least one association
        has_association = True in self.cleaned_data.values()

        if not has_association:
            raise ValidationError("At least one association needs to be chosen.")

        return cleaned_data

    def save(self, user=None):
        """Saves the association links by creating or removing UserMembership instances."""
        if not self.user and not user:
            raise ValueError("Both self.user and user are None")
        if user is None:
            user = self.user

        for key, value in self.cleaned_data.items():
            link = self.fields[key].get_membership_model(user, new_value=value)
            if value:
                if link.id is None:
                    link.save()
                elif link.get_verified_state() is False:
                    # If user was rejected, and a new request is entered
                    link.verified_on = None
                    link.save()
            else:
                if link and link.get_verified_state() is not False:
                    link.delete()


class AssociationSettingsForm(forms.ModelForm):
    class Meta:
        model = Association
        fields = ('balance_update_instructions', 'invoicing_method')
        help_texts = {
            'invoicing_method': "How members will be invoiced. Only applicable if association can invoice members."
                                " For instance 'Q-rekening' in the case of Quadrivium.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.allow_invoicing:
            self.fields['invoicing_method'].disabled = True
        else:
            self.fields['invoicing_method'].required = True
