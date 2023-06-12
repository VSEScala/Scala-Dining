from django import forms
from django.contrib.auth.forms import UserCreationForm, UsernameField
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.forms import ModelForm

from userdetails.models import Association, User, UserMembership


class RegisterUserForm(UserCreationForm):
    # Previously associations were saved using a separate AssociationLinkForm. During user creation the logic is so
    # simple that is suffices to have a simple multiple choice field with all associations and create (unverified)
    # memberships on save.
    #
    # By default, this field is required.
    associations = forms.ModelMultipleChoiceField(
        queryset=Association.objects.filter(is_choosable=True),
        widget=forms.CheckboxSelectMultiple(),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "password1",
            "password2",
            "email",
            "first_name",
            "last_name",
            "allergies",
        )
        field_classes = {
            "username": UsernameField
        }  # This adds HTML attributes for semantics, see UserCreationForm.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

        # Set headings used during rendering.
        #
        # I don't like doing this here instead of in the template or view, but
        # I don't know how to do that cleanly.
        self.fields["username"].heading = "Account details"
        self.fields["first_name"].heading = "Personal details"
        self.fields["associations"].heading = "Memberships"

    def save(self, commit=True):
        """Saves user and creates the memberships."""
        user = super().save(commit=False)
        if commit:
            with transaction.atomic():
                user.save()
                for association in self.cleaned_data["associations"]:
                    UserMembership.objects.create(
                        related_user=user, association=association
                    )
        return user


class UserForm(ModelForm):
    name = forms.CharField(required=False)

    class Meta:
        model = User
        fields = ("username", "name", "email", "allergies")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].disabled = True
        self.fields["name"].initial = str(self.instance)
        self.fields[
            "name"
        ].help_text = "Contact the site administrator if you want to change your name."
        self.fields["email"].disabled = True
        self.fields["email"].required = False  # To hide the asterisk.

        # Define a heading used during rendering the form.
        self.fields["allergies"].heading = "Dining"


class AssociationLinkForm(forms.Form):
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Get choosable associations and associations the user is already a member of.
        #
        # 'distinct' is necessary because otherwise there will be a large
        # number of duplicate associations returned, resulting in a slow page
        # load.
        associations = (
            Association.objects.filter(
                Q(is_choosable=True) | Q(usermembership__related_user=user)
            )
            .distinct()
            .order_by("slug")
        )

        for association in associations:
            # Find membership.
            try:
                membership = UserMembership.objects.get(
                    related_user=user, association=association
                )
            except UserMembership.DoesNotExist:
                membership = None

            # Construct boolean field for the association.
            field = forms.BooleanField(
                required=False,
                label=association.name,
                # Disable when the membership is frozen.
                disabled=membership and membership.is_frozen(),
                # Set checked when there is a membership, and it is not rejected.
                initial=membership and not membership.is_rejected(),
            )

            # Attach membership and association to the field, which is used by the view.
            field.membership = membership
            field.association = association
            self.fields[association.slug] = field

    def clean(self):
        cleaned_data = super().clean()
        # Check if user is assigned to at least one association
        has_association = True in self.cleaned_data.values()

        if not has_association:
            raise ValidationError("At least one association needs to be chosen")

        return cleaned_data

    def save(self):
        """Saves the memberships."""
        if self.errors:
            # This is to make it behave the same way as the ModelForm.save() method.
            raise ValueError("The form didn't validate.")

        for key, chosen in self.cleaned_data.items():
            membership = self.fields[key].membership
            association = self.fields[key].association

            # Selected but no membership exists, we need to create it.
            if chosen and not membership:
                UserMembership.objects.create(
                    related_user=self.user, association=association
                )

            # Selected but the membership was rejected, set as pending.
            #
            # (Because Django checks for the disabled state server-side, this
            # can only happen when the membership state is not frozen.)
            if chosen and membership and membership.is_rejected():
                membership.set_pending()
                membership.save()

            # Not selected but there is a non-rejected membership, we need to delete it.
            if not chosen and membership and not membership.is_rejected():
                membership.delete()


class AssociationSettingsForm(forms.ModelForm):
    class Meta:
        model = Association
        fields = ["balance_update_instructions"]
