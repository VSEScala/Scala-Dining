from django.db.models.signals import post_save
from django.dispatch import receiver

from creditmanagement.models import PendingDiningListTracker
from dining.models import DiningList


@receiver(post_save, sender=DiningList)
def create_pending_dining_list_tracker(sender, instance=False, created=False, **kwargs):
    """Creates a new PendingDiningListTracker when a new dining list is added."""
    if created:
        PendingDiningListTracker(dining_list=instance).save()
