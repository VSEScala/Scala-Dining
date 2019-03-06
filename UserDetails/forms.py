from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.db.utils import OperationalError
from django.db.models import Q
from django.forms import ModelForm
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from Dining.models import UserDiningSettings
from .models import User, Association, UserMembership


class RegisterUserForm(UserCreationForm):
    password2 = forms.CharField(widget=forms.PasswordInput, label="Password confirmation")

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'email')

    def clean_email(self):
        cleaned_email = self.cleaned_data['email']
        if User.objects.filter(email=cleaned_email).exists():
            msg = 'E-mail is already used. Did you forget your password?'
            raise ValidationError(msg)
        return cleaned_email


class RegisterUserDetails(forms.ModelForm):
    first_name = forms.CharField(max_length=40, required=True)
    last_name = forms.CharField(max_length=40, required=True)
    allergies = forms.CharField(max_length=100, required=False, help_text="Max 100 characters, leave empty if none")

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'allergies']

    def save_as(self, user):
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        user.userdiningsettings.allergies = self.cleaned_data.get('allergies')
        user.save()
        user.userdiningsettings.save()


class RegisterAssociationLinks(forms.Form):
    # Todo? Could change the widget to e.g. checkboxes
    try:
        associations = forms.MultipleChoiceField(
            choices=[(a.pk, a.name) for a in Association.objects.filter(is_choosable=True)],
            help_text='At which associations are you active?',
            widget=forms.CheckboxSelectMultiple)
        # In case associations table did not exist yet, except the operation
    except OperationalError:
        pass

    def create_links_for(self, user):
        for association in self.cleaned_data['associations']:
            UserMembership.objects.create(related_user=user, association_id=association)


class DiningProfileForm(ModelForm):
    class Meta:
        model = UserDiningSettings
        fields = ['allergies']


class UserForm(ModelForm):
    name = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ['username', 'name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].disabled = True
        self.fields['name'].initial = self.instance
        self.fields['email'].disabled = True


class AssociationLinkField(forms.BooleanField):
    """
    A special BooleanField model for association links.
    Can also indicate current validation state and auto-sets initial value
    """
    def __init__(self, user, association, *args, **kwargs):
        super(AssociationLinkField, self).__init__(*args, **kwargs)

        self.initial = False
        self.required = False
        self.label = association.name
        self.user = user
        self.association = association

        # Find the membership, if any
        if user is not None:
            try:
                self.membership = association.usermembership_set.get(related_user=user)
                self.initial = self.membership.is_member()
                if not self.membership.is_member():
                    # There is a link object, but he's not a member, so block it
                    self.disabled = True
            except ObjectDoesNotExist:
                self.membership = None
        if association is None:
            raise ValueError("Association can not be None")

    def verified(self):
        if self.membership is None:
            return None
        return self.membership.get_verified_state()

    def get_membership_model(self, user=None, new_value=True):
        # Check input data for correctness
        if self.user is None and user is None:
            raise ValueError("Field does not contain user and user was not given in method")
        if user is not None and self.user != user:
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
            except ObjectDoesNotExist:
                if new_value:
                    return UserMembership(related_user=user, association=self.association)
        return None


class AssociationLinkForm(forms.Form):

    def __init__(self, user, *args, **kwargs):
        super(AssociationLinkForm, self).__init__(*args, **kwargs)

        self.user = user

        # Get all associations and make a checkbox field
        for association in Association.objects.filter(
                Q(is_choosable=True) |
                (Q(is_choosable=False) & Q(usermembership__related_user=user))) \
                .distinct().order_by('slug'):

            field = AssociationLinkField(user, association)

            self.fields[association.name] = field

    def save(self):
        """
        Saves the association links. Removes
        :return:
        """
        for key, value in self.cleaned_data.items():
            link = self.fields[key].get_membership_model(self.user, new_value=value)
            if value:
                if link.id is None:
                    link.save()
            else:
                if link is not None and link.get_verified_state() != False:
                    link.delete()