from django.db.models.signals import post_save
from django.dispatch import receiver

from CreditManagement.models import PendingDiningListTracker
from Dining.models import DiningList


@receiver(post_save, sender=DiningList)
def create_association_credit(sender, instance=False, created=False, **kwargs):
    """Create a new PendingDiningListTracker when a new dining list is added.

    Args:
        sender: The sender instance.
        instance: The dining_list instance.
        created: Whether this save caused the instance to be created.
        **kwargs
    """
    if created:
        PendingDiningListTracker(dining_list=instance).save()
