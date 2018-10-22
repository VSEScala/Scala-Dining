from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Association, UserMemberships


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
