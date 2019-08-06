from allauth.socialaccount.models import SocialApp
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    email = models.EmailField(_('email address'), unique=True)
    is_suspended = models.BooleanField(default=False, verbose_name="Whether this user is suspended from using the site")
    is_banned = models.BooleanField(default=False, verbose_name="Whether this account is banned")
    deactivation_reason = models.CharField(default="", blank=True, max_length=256)

    def __str__(self):
        name = self.first_name + " " + self.last_name
        if name == " ":
            return "@" + self.username
        else:
            return name

    @cached_property
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
        """Return if user is a board member of association identified by id"""
        return self.groups.filter(id=associationId).count() > 0

    def is_verified_member_of(self, association):
        """Return if the user is a verified member of the association"""
        return self.get_verified_memberships().filter(association=association).exists()

    def get_verified_memberships(self):
        return self.usermembership_set.filter(is_verified=True)

    def has_min_balance_exception(self):
        """Whether this user is allowed unlimited debt. For this, the association membership must be verified"""
        exceptions = [membership.association.has_min_exception for membership in self.get_verified_memberships()]
        return True in exceptions

    def suspend(self, reason="", undo=False):
        if self.is_banned:
            return
        if undo:
            self.is_suspended = False
            self.deactivation_reason = ""
            self.save()
        else:
            self.is_suspended = True
            self.deactivation_reason = reason
            self.save()


class Association(Group):
    slug = models.SlugField(max_length=10)
    image = models.ImageField(blank=True, null=True)
    icon_image = models.ImageField(blank=True, null=True)
    is_choosable = models.BooleanField(default=True,
                                       help_text="If checked, this association can be chosen as membership by users")
    has_min_exception = models.BooleanField(default=False,
                                            help_text="If checked, this association has an exception to the minimum balance")
    social_app = models.ForeignKey(SocialApp, on_delete=models.PROTECT, null=True, blank=True,
                                   help_text='A user automatically becomes member of the association if she signs up using this social app')
    balance_update_instructions = models.TextField(max_length=512, default="to be defined")

    @cached_property
    def requires_action(self):
        """Whether some action needs to be done by the board. Used for display of notifications on the site"""
        return self.has_new_member_requests()

    def has_new_member_requests(self):
        return UserMembership.objects.filter(association=self, verified_on__isnull=True).exists()

    class Meta:
        permissions = [
            ("has_suspended_user_screen", "Whether this association can see the suspended users"),
            ("has_system_credit_screen", "Whether this association can watch the system balance screen"),
        ]


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

    def set_verified(self, verified):
        """Set the verified state to the value of verified (True or False) and set verified_on to now and save"""
        self.is_verified = verified
        self.verified_on = timezone.now()
        self.save()

        # Check if the user still has access rights
        suspend_reason = "You do not have any verified memberships"
        if verified:
            if self.related_user.deactivation_reason == suspend_reason:
                self.related_user.suspend(undo=True)
        else:
            # If not verified, check if the user has any (open) verifications at other associations
            open_memberships = self.related_user.usermembership_set.exclude(is_verified=False, verified_on__isnull=False)
            if not open_memberships.exists():
                self.related_user.suspend(reason=suspend_reason)

