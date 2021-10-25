from allauth.socialaccount.models import SocialApp
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property


class User(AbstractUser):
    # Email override to make it unique and required
    email = models.EmailField("email address", unique=True)

    # 'dietary requirements' seems to be the most common terminology according to
    # https://interpersonal.stackexchange.com/questions/18928/what-is-the-etiquette-for-asking-whether-someone-has-a-special-diet
    dietary_requirements = models.CharField(
        max_length=100,
        blank=True,
        help_text="E.g. gluten or vegetarian. Leave empty if not applicable.",
        verbose_name="food allergies or preferences"
    )
    allow_grocery_payments = models.BooleanField(
        default=True,
        help_text="Whether to allow automatic grocery payments from your account balance."
                  " You will always be notified and can always undo these transactions.",
    )

    def __str__(self):
        return "{} {}".format(self.first_name, self.last_name).strip() or "@{}".format(self.username)

    def is_verified(self):
        """Whether this user is verified as part of a Scala association."""
        links = UserMembership.objects.filter(related_user=self)

        for membership in links:
            if membership.is_verified:
                return True
        return False

    @cached_property
    def boards(self):
        """Returns all associations of which this member has board access."""
        return Association.objects.filter(user=self).all()

    @cached_property
    def requires_action(self):
        """Whether some action is required by the user."""
        for board in self.boards:
            if board.requires_action:
                return True
        return False

    @cached_property
    def requires_information_updates(self):
        from general.views import SiteUpdateView
        return SiteUpdateView.has_new_update(self)

    @cached_property
    def requires_information_rules(self):
        from general.views import RulesPageView
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

    def is_board_of(self, association_id):
        """Returns if user is a board member of association identified by given id."""
        return self.groups.filter(id=association_id).exists()

    def is_verified_member_of(self, association):
        """Returns if the user is a verified member of the association."""
        return self.get_verified_memberships().filter(association=association).exists()

    def get_verified_memberships(self):
        return self.usermembership_set.filter(is_verified=True)

    # Todo: deprecated
    def has_min_balance_exception(self):
        """Whether this user is allowed unlimited debt.

        For this to hold, the association membership must be verified.
        """
        exceptions = [membership.association.has_min_exception for membership in self.get_verified_memberships()]
        return any(exceptions)

    def can_use_direct_debit(self) -> bool:
        """Returns true of user is member of an association which allows direct debit."""
        return Association.objects.filter(usermembership__in=self.get_verified_memberships(),
                                          allow_direct_debit=True).exists()


class Association(Group):
    slug = models.SlugField(max_length=10)
    image = models.ImageField(blank=True, null=True)
    icon_image = models.ImageField(blank=True, null=True)
    is_choosable = models.BooleanField(default=True,
                                       help_text="If checked, this association can be chosen as membership by users.")
    allow_direct_debit = models.BooleanField(
        default=False,
        help_text="If checked, members can upgrade their balance using a direct debit transaction.")
    direct_debit_name = models.CharField(blank=True,
                                         max_length=100,
                                         help_text="For instance Q-rekening in the case of Quadrivium.")
    social_app = models.ForeignKey(SocialApp, on_delete=models.PROTECT, null=True, blank=True,
                                   help_text="A user automatically becomes member of the association "
                                             "if they sign up using this social app.")
    balance_update_instructions = models.TextField(max_length=512, default="to be defined")
    has_site_stats_access = models.BooleanField(default=False)

    @cached_property
    def requires_action(self):
        """Whether some action needs to be done by the board.

        Used for display of notifications on the site.
        """
        return self.has_new_member_requests()

    def has_new_member_requests(self):
        return UserMembership.objects.filter(association=self, verified_on__isnull=True).exists()


class UserMembership(models.Model):
    """Stores membership information."""

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
        """Sets the verified state to the value of verified (True or False) and set verified_on to now and save."""
        self.is_verified = verified
        self.verified_on = timezone.now()
        self.save()
