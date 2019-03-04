from decimal import Decimal, Context, Inexact

from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property


class User(AbstractUser):
    # Field that can be used to link a user account to a user account in an external system such as OpenID Connect.
    # Should contain something like a UUID.
    external_link = models.CharField(max_length=150, editable=False, default="",
                                     help_text="When this is set, the account is linked to an external system.")

    def __str__(self):
        name = self.first_name + " " + self.last_name
        if name == " ":
            return "@" + self.username
        else:
            return name

    def is_verified(self):
        """
        Whether this user is verified as part of a Scala association
        """
        links = UserMembership.objects.filter(related_user=self)

        for membership in links:
            if membership.is_verified:
                return True
        return False

    def can_access_back(self):
        is_a_boardmember = (self.groups.count() > 0)
        return self.is_staff or is_a_boardmember

    @cached_property
    def boards(self):
        """
        Returns all associations of which this member has board access
        :return: A queryset of all associations on which this member is board member
        """
        return Association.objects.filter(user=self).all()

    @cached_property
    def requires_action(self):
        """
        Whether some action is required by the user
        :return: True or False
        """
        for board in self.boards:
            if board.requires_action:
                return True

        return False

    @cached_property
    def requires_information(self):
        if self.requires_information_rules:
            return True
        if self.requires_information_updates:
            return True
        return False

    @cached_property
    def requires_information_updates(self):
        from General.views import SiteUpdateView
        return SiteUpdateView.has_new_update(self)

    @cached_property
    def requires_information_rules(self):
        from General.views import RulesPageView
        return RulesPageView.has_new_update(self)

    @cached_property
    def is_staff(self):
        # For each group the member is part of, if it has permissions
        for group in self.groups.all():
            if group.permissions.count() > 0:
                return True
        if self.user_permissions.count() > 0:
            return True
        if self.is_superuser:
            return True
        return False


class Association(Group):
    slug = models.SlugField(max_length=10)
    image = models.ImageField(blank=True)
    is_choosable = models.BooleanField(default=True, verbose_name="Whether this association can be chosen as membership by users")

    @cached_property
    def requires_action(self):
        """
        Whether some action needs to be done by the board. Used for display of notifications on the site
        :return: True or false
        """
        return self.has_new_member_requests

    @cached_property
    def has_new_member_requests(self):
        return UserMembership.objects.filter(
            association=self.association,
            verified_on__isnull=True).count() > 0

class UserMembership(models.Model):
    """
    Stores membership information
    """
    related_user = models.ForeignKey(User, on_delete=models.CASCADE)
    association = models.ForeignKey(Association, on_delete=models.CASCADE)
    is_verified = models.BooleanField(default=False)
    verified_on = models.DateTimeField(blank=True, null=True, default=None)
    created_on = models.DateTimeField(default=timezone.now)
