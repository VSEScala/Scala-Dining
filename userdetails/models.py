from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from phonenumber_field.modelfields import PhoneNumberField


class User(AbstractUser):
    # Email override to make it unique and required
    email = models.EmailField("e-mail address", unique=True)

    # 'dietary requirements' seems to be the most common terminology according to
    # https://interpersonal.stackexchange.com/questions/18928/what-is-the-etiquette-for-asking-whether-someone-has-a-special-diet
    dietary_requirements = models.CharField(
        max_length=100,
        blank=True,
        help_text="E.g. gluten or vegetarian. Leave empty if not applicable.",
        verbose_name="food allergies or preferences"
    )

    # Lets use PhoneNumberField instead of CharField so that the user gets a phone number input widget
    # and it's checked for errors, as well as it prevents abuse of the field for non-phone number data.
    phone_number = PhoneNumberField(blank=True, help_text="If given, will be visible to other diners on the same list.")
    email_public = models.BooleanField(
        'e-mail public',
        default=False,
        help_text="If selected, your e-mail address will be visible to other diners on the same list.")

    def __str__(self):
        return "{} {}".format(self.first_name, self.last_name).strip() or "@{}".format(self.username)

    def is_verified(self):
        """Whether this user is verified as part of a Scala association."""
        links = UserMembership.objects.filter(related_user=self)

        for membership in links:
            if membership.is_verified():
                return True
        return False

    is_verified.boolean = True

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

    def is_board_of(self, association_id):
        """Returns if user is a board member of association identified by given id."""
        return self.groups.filter(id=association_id).exists()

    def is_verified_member_of(self, association):
        """Returns if the user is a verified member of the association."""
        return self.get_verified_memberships().filter(association=association).exists()

    def get_verified_memberships(self):
        return self.usermembership_set.filter(verified_state=True)

    def can_use_invoicing(self) -> bool:
        """Returns true of user is member of an association which allows invoicing."""
        return Association.objects.filter(usermembership__in=self.get_verified_memberships(),
                                          allow_invoicing=True).exists()


class Association(Group):
    slug = models.SlugField(max_length=10)
    image = models.ImageField(blank=True, null=True)
    icon_image = models.ImageField(blank=True, null=True)
    is_choosable = models.BooleanField(default=True,
                                       help_text="If checked, this association can be chosen as membership by users.")
    allow_invoicing = models.BooleanField(
        default=False,
        help_text="If checked, members can upgrade their balance by having the association invoice them.")
    invoicing_method = models.CharField(
        'invoicing method name',
        blank=True,
        max_length=100,
        help_text="Name of the invoicing method. For instance 'Q-bill' in the case of Quadrivium.")
    invoicing_description = models.TextField(
        blank=True,
        help_text='Description of how members will be invoiced. For Q-bill it will be something like '
                  '"twice a year the amount will be deducted from your bank account using direct debit."',
    )

    social_app = models.ForeignKey(SocialApp, on_delete=models.PROTECT, null=True, blank=True,
                                   help_text="A user automatically becomes member of the association "
                                             "if they sign up using this social app.")
    balance_update_instructions = models.TextField(max_length=512, default="to be defined")
    has_site_stats_access = models.BooleanField(default=False)

    class Meta:
        ordering = ('slug',)

    @cached_property
    def requires_action(self):
        """Whether some action needs to be done by the board.

        Used for display of notifications on the site.
        """
        return self.member_requests().exists()

    def member_requests(self):
        """Returns a QuerySet of pending membership requests."""
        return UserMembership.objects.filter(association=self, verified_state=None)


class UserMembership(models.Model):
    """Stores membership information."""

    related_user = models.ForeignKey(User, on_delete=models.CASCADE)
    association = models.ForeignKey(Association, on_delete=models.CASCADE)
    # True=verified, False=rejected, None=pending (not yet verified or rejected)
    verified_state = models.BooleanField(null=True)
    verified_last_change = models.DateTimeField(null=True)
    created_on = models.DateTimeField(default=timezone.now)

    def is_verified(self):
        return self.verified_state is True

    def is_rejected(self):
        return self.verified_state is False

    def is_pending(self):
        return self.verified_state is None

    def __str__(self):
        return "{user} - {association}".format(user=self.related_user, association=self.association)

    def set_verified(self, state=True):
        self.verified_state = state
        self.verified_last_change = timezone.now()
        self.save()

    def is_frozen(self):
        """A membership is frozen, i.e. can't be changed, if it was verified or rejected too recently."""
        if not self.verified_last_change:
            return False
        return timezone.now() - self.verified_last_change < settings.MEMBERSHIP_FREEZE_PERIOD
