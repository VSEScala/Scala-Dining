from allauth.account.forms import ChangePasswordForm, ResetPasswordKeyForm
from django.utils.translation import gettext as _


class CustomChangePasswordForm(ChangePasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["oldpassword"].label = _("Current password")
        self.fields["password1"].label = _("New password")
        self.fields["password2"].label = _("New password (again)")


class CustomResetPasswordKeyForm(ResetPasswordKeyForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = _("New password")
        self.fields["password2"].label = _("New password (again)")
