from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group

from .models import User, UserMembership, Association


class AssociationLinks(admin.TabularInline):
    """
    Create the membership information on the User page
    """
    model = UserMembership
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
        a = UserMembership.objects.filter(association=self.value()).values_list('related_user_id')

        # Crosslink the given user identities with the given query
        return queryset.filter(pk__in=a)


class BoardFilter(admin.RelatedOnlyFieldListFilter):

    def __init__(self, *args, **kwargs):
        super(admin.RelatedOnlyFieldListFilter, self).__init__(*args, **kwargs)
        self.title = 'Boardmembers'


class UserOverview(User):
    class Meta:
        proxy = True


class CustomUserAdmin(admin.ModelAdmin):
    """
    Set up limited view of the user page
    """

    list_display = ('username', 'first_name', 'last_name', 'is_verified', 'last_login')
    list_filter = [MemberOfFilter, ('groups', BoardFilter)]

    readonly_fields = ('date_joined', 'last_login')
    inlines = [AssociationLinks]
    fields = ('username', ('first_name', 'last_name'), 'date_joined', 'email')


class GroupAdminForm(forms.ModelForm):
    """
    Creates a multi-select form for the members in teh group panel
    ( opposed to Djangos standard location: in the user page)
    """
    users = forms.ModelMultipleChoiceField(
        User.objects.all(),
        widget=admin.widgets.FilteredSelectMultiple('Users', False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

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
    Create the model for the groups page.
    """
    exclude = ['permissions']
    form = GroupAdminForm


admin.site.register(UserOverview, CustomUserAdmin)
admin.site.register(User, UserAdmin)
admin.site.register(Association, AssociationAdmin)
admin.site.register(UserMembership)