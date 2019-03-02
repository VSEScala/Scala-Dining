from django import forms
from django.forms import ModelForm
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import User, Association, UserMembership
from Dining.models import UserDiningSettings
from django.db.utils import OperationalError


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Gebruikersnaam",
        max_length=80,
        required=True,
    )

    password = forms.CharField(
        widget=forms.PasswordInput,
        label="Wachtwoord",
        required=True
    )


class RegisterUserForm(UserCreationForm):
    password2 = forms.CharField(widget=forms.PasswordInput, label="Password confirmation")

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2', 'email')

    def clean(self):
        # Check if the email is not already used.
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            msg = 'E-mail is already used.'
            self._errors['email'] = self.error_class([msg])
            del self.cleaned_data['email']
        return self.cleaned_data


class RegisterUserDetails(forms.ModelForm):
    first_name = forms.CharField(max_length=40, required=True)
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
            help_text='At which associations are you active?')
        # In case associations table did not exist yet, except the operation
    except OperationalError:
        pass

    def create_links_for(self, user):
        for association in self.cleaned_data['associations']:
            UserMembership.objects.create(related_user=user, association_id=association)


class SettingsEssentialsForm(ModelForm):
    password_prev = forms.CharField(widget=forms.PasswordInput, required=False, label="Current password")
    password_new = forms.CharField(widget=forms.PasswordInput, required=False, label="New password",
                                   help_text="Leave empty if you don't want to change password")
    password_check = forms.CharField(widget=forms.PasswordInput, required=False, label="Repeat new password")

    class Meta:
        model = User
        fields = ('username', 'email', 'password_prev', 'password_new', 'password_check')

    def clean(self):

        # If the password needs to be changed (i.e. a new password is given
        if len(self.data['password_new']) > 0:
            user = authenticate(username=self.instance.username, password=self.data['password_prev'])
            if user is None:
                self.add_error('password_prev', "Password is not correct")
                return
            else:
                if self.cleaned_data['password_new'] != self.cleaned_data['password_check']:
                    self.add_error('password_check', "Passwords do not match")
                    return

        super(SettingsEssentialsForm, self).clean()

    def save(self, commit=True):
        super(SettingsEssentialsForm, self).save()

        if len(self.data['password_new']) > 0:
            self.instance.set_password(self.cleaned_data["password_new"])

        if commit:
            self.instance.save()


class Settings_Dining_Form(ModelForm):
    class Meta:
        model = UserDiningSettings
        exclude = ('user',)
