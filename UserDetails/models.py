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

    # Todo: move balance to CreditManagement app
    @cached_property
    def balance(self):
        # Calculate sum of target minus sum of source
        from CreditManagement.models import AbstractTransaction
        balance = AbstractTransaction.get_user_balance(self)

        # Convert to two decimals in an exact manner
        return balance.quantize(Decimal('0.01'), context=Context(traps=[Inexact]))

    def can_access_back(self):
        is_a_boardmember = (self.groups.count() > 0)
        return self.is_staff or is_a_boardmember


class Association(Group):
    slug = models.SlugField(max_length=10)
    image = models.ImageField(blank=True)


class UserMembership(models.Model):
    """
    Stores membership information
    """
    related_user = models.ForeignKey(User, on_delete=models.CASCADE)
    association = models.ForeignKey(Association, on_delete=models.CASCADE)
    is_verified = models.BooleanField(default=False)
    verified_on = models.DateTimeField(blank=True, null=True, default=None)
    created_on = models.DateTimeField(default=timezone.now)
