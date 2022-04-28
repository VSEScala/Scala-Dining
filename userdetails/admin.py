from allauth.account.models import EmailAddress
from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group

from general.mail_control import send_templated_mail
from userdetails.models import User, UserMembership, Association


class MembershipInline(admin.TabularInline):
    """Membership inline."""
    model = UserMembership
    extra = 0
    readonly_fields = ('created_on',)


class BoardListFilter(admin.RelatedFieldListFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "board membership"


class GroupAdminForm(forms.ModelForm):
    """Creates a multi-select form for the members in the group.

    (As opposed to Djangos standard location in the user page.)
    """
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=FilteredSelectMultiple(verbose_name='users', is_stacked=False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['users'].initial = self.instance.user_set.all()

    def save(self, *args, **kwargs):
        kwargs['commit'] = True
        return super().save(*args, **kwargs)

    def save_m2m(self):
        self.instance.user_set.set(self.cleaned_data['users'])


@admin.register(Association)
class AssociationAdmin(admin.ModelAdmin):
    exclude = ('permissions',)
    form = GroupAdminForm


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Adjusted UserAdmin.

    Staff and permission fields are removed (is_staff, user_permissions)
    because we don't use them, we only use is_superuser.

    See the super class (UserAdmin) for the defaults.
    """
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Settings', {'fields': ('dietary_requirements', 'email_public', 'phone_number')}),
        ('Permissions', {
            'fields': ('is_active', 'is_superuser'),
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'first_name', 'last_name', 'is_verified', 'last_login', 'is_superuser')
    # Note: the membership filter also includes membership which are 'verified not a member of'
    list_filter = ('is_superuser', 'is_active', 'usermembership__association', ('groups', BoardListFilter))
    readonly_fields = ('last_login', 'date_joined')

    inlines = (MembershipInline,)

    def send_test_mail(self, request, queryset):
        send_templated_mail('mail/test', queryset, request=request)

    actions = [send_test_mail]


# From allauth
admin.site.unregister(EmailAddress)

# Hide groups because we only use the Association model for groups
admin.site.unregister(Group)
