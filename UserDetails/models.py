from django.db import models
from django.contrib.auth.models import AbstractUser, Group


# Create your models here.

class User(AbstractUser):

    def __str__(self):
        name = self.first_name + " " + self.last_name
        if name == " ":
            return "@-"+self.username
        else:
            return name\

    def is_verified(self):
        """
        Check if the account is verified by assessing all linked associations
        :return: Whether the user is verified
        """
        return self.details.is_verified()

    def get_credit_containing_instance(self):
        return self.usercredit

    def can_access_back(self):
        is_a_boardmember = (self.groups.count() > 0)
        return self.is_staff or is_a_boardmember



class Association(Group):
    """
    Create a meta class to obtain personal names instead of usernames
    """
    class Meta:
        proxy = True

    def get_credit_containing_instance(self):
        return self.associationcredit_set.get(end_date=None)


class AssociationDetails(models.Model):
    association = models.OneToOneField(Association, on_delete=models.CASCADE, primary_key=True)
    image = models.ImageField()
    shorthand = models.SlugField(max_length=10)


class UserDetail(models.Model):
    """
    Contains several small personal details of the user
    """
    related_user = models.OneToOneField(User, related_name="details", on_delete=models.CASCADE, primary_key=True)
    phone_number = models.CharField(max_length=15, blank=True)
    profile_img = models.ImageField(blank=True)
    profile_color = models.CharField(max_length=20, blank=True)

    # Check if the account is verified by assessing all linked associations
    def is_verified(self):
        """
        Whether this user is verified as part of a Scala association
        :return:
        """
        links = UserMemberships.objects.filter(related_user=self.related_user)

        verified = False
        for membership in links.all():
            if membership.is_verified:
                verified = True
        return verified

    def __str__(self):
        name = self.related_user.first_name + " " + self.related_user.last_name
        if name == " ":
            return "@-"+self.related_user.username
        else:
            return name


class UserMemberships(models.Model):
    """
    Stores membership information
    """
    related_user = models.ForeignKey(User, on_delete=models.CASCADE)
    association = models.ForeignKey(Association, on_delete=models.CASCADE)
    is_verified = models.BooleanField(default=False)
    verified_on = models.DateField(blank=True, null=True, default=None)
    created_on = models.DateField(auto_created=True, blank=True, null=True)
