from allauth.account.models import EmailAddress
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from general.mail_control import send_templated_mail
from userdetails.models import Association, User, UserMembership


class AssociationLinks(admin.TabularInline):
    """Membership inline."""

    model = UserMembership
    extra = 0


class MemberOfFilter(admin.SimpleListFilter):
    """Creates a filter that filters users on the association they are part of (unvalidated)."""

    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = "Member of association"

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "associationmember"

    def lookups(self, request, model_admin):
        """Returns a list of tuples representing all the associations as displayed in the table."""
        return Association.objects.all().values_list(
            "pk",
            "name",
        )

    def queryset(self, request, queryset):
        """Returns the filtered querysets containing all members of the selected associations."""
        if self.value() is None:
            return queryset

        # Find all members in the UserMemberships model containing the selected association
        a = UserMembership.objects.filter(association=self.value()).values_list(
            "related_user_id"
        )
        return queryset.filter(pk__in=a)


class BoardFilter(admin.RelatedOnlyFieldListFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = "board members"


class UserOverview(User):
    class Meta:
        proxy = True


@admin.register(UserOverview)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("username", "first_name", "last_name", "is_verified", "last_login")
    list_filter = [MemberOfFilter, ("groups", BoardFilter)]

    readonly_fields = ("date_joined", "last_login")
    inlines = [AssociationLinks]
    fields = ("username", ("first_name", "last_name"), "date_joined", "email")

    def send_test_mail(self, request, queryset):
        send_templated_mail("mail/test", queryset, request=request)

    actions = [send_test_mail]


class GroupAdminForm(forms.ModelForm):
    """Creates a multi-select form for the members in the group.

    (As opposed to Djangos standard location in the user page.)
    """

    users = forms.ModelMultipleChoiceField(
        User.objects.all(),
        widget=admin.widgets.FilteredSelectMultiple("Users", False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # find the users part of the group
        if self.instance.pk:
            initial_users = self.instance.user_set.values_list("pk", flat=True)
            self.initial["users"] = initial_users

    def save(self, *args, **kwargs):
        kwargs["commit"] = True
        return super(GroupAdminForm, self).save(*args, **kwargs)

    def save_m2m(self):
        self.instance.user_set.clear()
        self.instance.user_set.add(*self.cleaned_data["users"])


@admin.register(Association)
class AssociationAdmin(admin.ModelAdmin):
    exclude = ["permissions"]
    form = GroupAdminForm


admin.site.register(User, UserAdmin)


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    """Allows viewing of group membership."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# From allauth
admin.site.unregister(EmailAddress)
