from allauth.account.models import EmailAddress
from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group

from userdetails.allergens import ALLERGENS
from userdetails.models import Association, InvalidEmail, User, UserMembership

# Association model


class BoardMembersForm(forms.ModelForm):
    """Creates a multi-select form for the board members in the group.

    (As opposed to Djangos standard location in the user page.)
    """

    board_members = forms.ModelMultipleChoiceField(
        User.objects.all(),
        widget=FilteredSelectMultiple("board members", False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # find the users part of the group
        if self.instance.pk:
            self.initial["board_members"] = self.instance.user_set.values_list(
                "pk", flat=True
            )

    def save(self, *args, **kwargs):
        # Not sure why but this seems necessary
        kwargs["commit"] = True
        return super().save(*args, **kwargs)

    def save_m2m(self):
        self.instance.user_set.clear()
        self.instance.user_set.add(*self.cleaned_data["board_members"])


@admin.register(Association)
class AssociationAdmin(GroupAdmin):
    fields = (
        "name",
        "short_name",
        "slug",
        "image",
        "icon_image",
        "is_choosable",
        "has_min_exception",
        "has_site_stats_access",
        "balance_update_instructions",
        "board_members",
        "permissions",
        "social_app",
    )
    form = BoardMembersForm


# User model


class MembershipInline(admin.TabularInline):
    model = UserMembership

    readonly_fields = ("is_verified", "verified_on", "created_on")
    extra = 0

    def has_change_permission(self, request, obj=None):
        return False


class EmailAddressInline(admin.TabularInline):
    model = EmailAddress
    extra = 0


class MemberOfFilter(admin.SimpleListFilter):
    """Creates a filter that filters users on the association they are part of (unvalidated)."""

    title = "membership"
    parameter_name = "associationmember"

    def lookups(self, request, model_admin):
        """Returns a list of tuples representing all the associations as displayed in the table."""
        return Association.objects.all().values_list("pk", "name")

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


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "is_verified", "last_login")
    list_filter = (
        MemberOfFilter,
        ("groups", BoardFilter),
        "is_superuser",
    )
    inlines = (MembershipInline, EmailAddressInline)
    fieldsets = (
        (
            None,
            {
                # Could also add `is_active`
                "fields": ("username", "password", "is_superuser")
            },
        ),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "email")},
        ),
        (
            "Food allergies or preferences",
            {
                "fields": (
                    *(a.model_field for a in ALLERGENS),
                    "other_allergy",
                    "food_preferences",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2", "email"),
            },
        ),
    )
    readonly_fields = ("date_joined", "last_login")


# Unregister Django group and allauth EmailAddress
admin.site.unregister(Group)
admin.site.unregister(EmailAddress)


@admin.register(InvalidEmail)
class InvalidEmailAdmin(admin.ModelAdmin):

    def has_change_permission(self, request, obj=None):
        return False
