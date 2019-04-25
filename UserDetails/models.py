from decimal import Decimal, Context, Inexact

from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    # Field that can be used to link a user account to a user account in an external system such as OpenID Connect.
    # Should contain something like a UUID.
    external_link = models.CharField(max_length=150, editable=False, default="",
                                     help_text="When this is set, the account is linked to an external system.")
    email = models.EmailField(_('email address'), unique=True)

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
    def requires_information_updates(self):
        from General.views import SiteUpdateView
        return SiteUpdateView.has_new_update(self)

    @cached_property
    def requires_information_rules(self):
        from General.views import RulesPageView
        return RulesPageView.has_new_update(self)

    def has_any_perm(self):
        """Returns true if the user has one or more permissions."""
        for group in self.groups.all():
            if group.permissions.count() > 0:
                return True
        if self.user_permissions.count() > 0:
            return True
        return False

    def has_admin_site_access(self):
        return self.is_active and (self.has_any_perm() or self.is_superuser)

    def is_board_of(self, associationId):
        '''
        Return if user is a board member of association identified by id
        '''
        return self.groups.filter(id=associationId).count() > 0

    def is_member_of(self, associationId):
        '''
        Return if the user is a member of the association identified by its id
        '''
        for m in UserMembership.objects.filter(related_user=self):
            if (m.association.id == associationId and m.is_verified):
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

    def get_verified_state(self):
        if self.is_verified:
            return True
        if self.verified_on is not None:
            return False
        return None

    def is_member(self):
        if not self.is_verified and self.verified_on:
            # It is not verified, but has verification date, so is rejected
            return False
        return True

    def __str__(self):
        return "{user} - {association}".format(user=self.related_user, association=self.association)
