from django.db.models.signals import post_save
from django.dispatch import receiver
from dining.models import DiningList
from creditmanagement.models import PendingDiningListTracker


"""""""""""""""""""""""""""""""""""""""""""""""""""
Spawn a new associationcredit when a new assocation is created
"""""""""""""""""""""""""""""""""""""""""""""""""""


@receiver(post_save, sender=DiningList)
def create_association_credit(sender, instance=False, created=False,  **kwargs):
    """
    Create a new PendingDiningListTracker when a new dining list is added
    :param sender:
    :param instance: The dining_list instance
    :param created: whether this save caused the instance to be created
    :param kwargs: not used
    """
    if created:
        PendingDiningListTracker(dining_list=instance).save()