from django import forms
from django.forms import ModelForm
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import User, Association, UserMemberships
from Dining.models import UserDiningSettings


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


class RegisterAssociationLinks(forms.Form):

    def __init__(self, *args, **kwargs):
        super(RegisterAssociationLinks, self).__init__(*args, **kwargs)

        #get the first argument
        postdetails = None
        if args is not None and len(args) > 0:
            postdetails = args[0]

            #Create the checkboxes for all associations
        for association in Association.objects.all():
            field_name = "association_"+str(association.id)

            # find argument in given arguments
            value = False
            if postdetails is not None:
                if postdetails.__contains__(field_name):
                    value = postdetails[field_name]

            self.fields[field_name] = forms.BooleanField(label=association.name, initial=value, required=False, label_suffix='')

    def clean(self):
        super(RegisterAssociationLinks, self).clean()

        #Check if at least one association is present
        for association in Association.objects.all():
            field_name = "association_"+str(association.id)

            if self.cleaned_data.get(field_name):
                return self.cleaned_data

        #no association link is present
        self.add_error(None, "You need to be member of at least one association")

    def create_links_for(self, user):
        for association in Association.objects.all():
            field_name = "association_"+str(association.id)

            if self.cleaned_data.get(field_name):
                # Signed up for this association
                UserMemberships(related_user=user, association=association).save()


class Settings_Essentials_Form(ModelForm):
    password_prev = forms.CharField(widget=forms.PasswordInput, required=False, label="Current password")
    password_new = forms.CharField(widget=forms.PasswordInput, required=False, label="New password", help_text="Leave empty if you don't want to change password")
    password_check = forms.CharField(widget=forms.PasswordInput, required=False, label="Repeat new password")

    class Meta:
        model = User
        fields = ('username', 'email', 'password_prev', 'password_new', 'password_check')

    def clean(self):

        # If the password needs to be changed (i.e. a new password is given
        if len(self.data['password_new'])>0:
            user = authenticate(username=self.instance.username, password=self.data['password_prev'])
            if user is None:
                self.add_error('password_prev', "Password is not correct")
                return
            else:
                if self.cleaned_data['password_new'] != self.cleaned_data['password_check']:
                    self.add_error('password_check', "Passwords do not match")
                    return
        else:
            print("No change")


        super(Settings_Essentials_Form, self).clean()

    def save(self, commit=True):
        super(Settings_Essentials_Form, self).save()

        if len(self.data['password_new'])>0:
            self.instance.set_password(self.cleaned_data["password_new"])

        if commit:
            self.instance.save()


class Settings_Dining_Form(ModelForm):

    class Meta:
        model = UserDiningSettings
        exclude = ('user', 'canSubscribeDiningList', 'canClaimDiningList')