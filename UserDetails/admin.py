from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserDetail, UserMemberships, Association, AssociationDetails
from CreditManagement.models import UserCredit
from django import forms


# Register your models here.

class UserDetailsLink(admin.StackedInline):
    """
    Create the additional information on the user page (taken from a new table)
    """
    model = UserDetail
    readonly_fields = ('is_verified',)
    can_delete = False
    verbose_name = ""
    verbose_name_plural = "More account info"

class UserCreditsLink(admin.StackedInline):
    """
    Show the credits of the user
    """
    model = UserCredit
    readonly_fields = ('credit',)
    can_delete = False
    verbose_name = ""
    verbose_name_plural = "money status"

class AssociationLinks(admin.TabularInline):
    """
    Create the membership information on the User page
    """
    model = UserMemberships
    min_num = 1
    extra = 0


class MemberOfFilter(admin.SimpleListFilter):
    """
    Creates a filter that filters users on the association they are part of (unvalidated)
    """
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Member of association'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'associationmember'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples representing all the associations
        as displayed in the table
        """

        return Association.objects.all().values_list('pk', 'name', )

    def queryset(self, request, queryset):
        """
        Returns the filtered querysets containing all members of the selected associations
        """

        # If no selection is made, return the entire query
        if self.value() is None:
            return queryset

        # Find all members in the UserMemberships model containing the selected association
        a = UserMemberships.objects.filter(association=self.value()).values_list('related_user_id')

        # Crosslink the given user identities with the given query
        return queryset.filter(pk__in=a)


class BoardFilter(admin.RelatedOnlyFieldListFilter):

    def __init__(self, *args, **kwargs):
        super(admin.RelatedOnlyFieldListFilter, self).__init__(*args, **kwargs)
        self.title = 'Boardmembers'


class CustomUserAdmin(UserAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('username', 'first_name', 'last_name', 'is_verified', 'last_login')
    list_filter = [MemberOfFilter, ('groups', BoardFilter)]

    readonly_fields = ('date_joined', 'last_login',)
    inlines = [UserDetailsLink, UserCreditsLink, AssociationLinks]
    # fields = ('username', ('first_name', 'last_name'), 'date_joined', 'email')


class AssociationDetailsLink(admin.StackedInline):
    model = AssociationDetails
    can_delete = False
    verbose_name = ""
    verbose_name_plural = "More account info"

class GroupAdminForm(forms.ModelForm):
    """
    Creates a multi-select form for the group panel (instead of users where the Django framework places it)
    """
    users = forms.ModelMultipleChoiceField(
        User.objects.all(),
        widget=admin.widgets.FilteredSelectMultiple('Users', False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(GroupAdminForm, self).__init__(*args, **kwargs)

        # find the users part of the group
        if self.instance.pk:
            initial_users = self.instance.user_set.values_list('pk', flat=True)
            self.initial['users'] = initial_users

    def save(self, *args, **kwargs):
        kwargs['commit'] = True
        return super(GroupAdminForm, self).save(*args, **kwargs)

    def save_m2m(self):
        self.instance.user_set.clear()
        self.instance.user_set.add(*self.cleaned_data['users'])


class AssociationAdmin(admin.ModelAdmin):
    """
    Create the model for the groups page
    """
    exclude = ['permissions', ]
    form = GroupAdminForm
    inlines = [AssociationDetailsLink]


"""
Unregister the basic User and Group page, re-register the new designs
"""
admin.site.register(User, CustomUserAdmin)
admin.site.register(Association, AssociationAdmin)

