from django.db.models.signals import post_save
from django.dispatch import receiver

from creditmanagement.models import PendingDiningListTracker, Account
from dining.models import DiningList
from userdetails.models import User, Association


@receiver(post_save, sender=DiningList)
def create_pending_dining_list_tracker(sender, instance=False, created=False, **kwargs):
    """Creates a new PendingDiningListTracker when a new dining list is added."""
    if created:
        PendingDiningListTracker(dining_list=instance).save()


@receiver(post_save, sender=User)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(user=instance)


@receiver(post_save, sender=Association)
def create_association_account(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(association=instance)
