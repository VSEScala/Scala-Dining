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


class AssociationLinkForm(forms.Form):

    def __init__(self, user, *args, **kwargs):
        super(AssociationLinkForm, self).__init__(*args, **kwargs)

        self.user = user

        # Get all associations and make a checkbox field
        for association in Association.objects.filter(
                Q(is_choosable=True) |
                (Q(is_choosable=False) & Q(usermembership__related_user=user)))\
                .distinct().order_by('slug'):

            try:
                link = association.usermembership_set.get(related_user=user)
            except ObjectDoesNotExist:
                link = None
            print(link)

            if link is not None:
                self.fields[association.name] = forms.BooleanField(label=association.name,
                                                                   required=False,
                                                                   initial=True)
                self.fields[association.name].validated = True
            else:
                self.fields[association.name] = forms.BooleanField(label=association.name,
                                                                   required=False,
                                                                   initial=False)
                self.fields[association.name].validated = False


    def save(self):
        for key, value in self.cleaned_data.items():
            try:
                link = UserMembership.objects.get(related_user=self.user, association__name=key)
            except ObjectDoesNotExist:
                link = None

            if link is not None and not value:
                # Remove an associationlink
                print("remove {0}".format(key))
            elif link is None and value:
                # Add an association link
                association = Association.objects.get(name=key)
                link = UserMembership(related_user=self.user, association=association)
                print("add {0}".format(key))