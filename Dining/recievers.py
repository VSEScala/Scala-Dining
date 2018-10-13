from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.db import transaction
from django.dispatch import receiver
from Dining.models import UserDiningSettings, UserDiningStats, DiningList, DiningEntry, DiningEntryExternal

from UserDetails.models import UserInformation
from django.contrib.auth.models import User
from django.db.models import F

"""""""""""""""""""""""""""""""""""""""""""""""""""
Adjust the credits due to dining list or related objects deletion
"""""""""""""""""""""""""""""""""""""""""""""""""""

@receiver(pre_delete, sender= DiningList)
def clear_list_funding(sender, instance=None, **kwargs):
    """
    When a complete dining_list is deleted, errors could occur due to the chain of recomputations after each DiningEntry
    deletion. To prevent this the dining_list auto reverts the cost to 0 reducing the number of credit recomputations
    to a single run_down.
    Note: if the Dining_list is already locked, this doesn't need to happen.
    :param sender: The DiningList class
    :param instance: The DiningList instance
    :param kwargs: not used in current implementation
    :return:
    """
    if instance.isAdjustable():
        instance.auto_pay = False
        instance.kitchen_cost = 0
        instance.save()

@receiver(post_delete,  sender=DiningEntry)
@receiver(post_delete, sender=DiningEntryExternal)
def on_entry_removal(sender, instance=None, **kwargs):
    """
    After deletion, correct the credit and other scores
    Only if the dining_list is still adjustable (unlocked)
    :param sender: The DiningEntry(External) class
    :param instance: The DiningEntry(External) instance
    :param kwargs: not used in current implementation
    :return:
    """
    if instance.dining_list.isAdjustable():
        # Revert the changes and costs
        dine_stats = instance.user.userdiningstats
        user_creds = instance.user.usercredit

        if sender == DiningEntry:
            dine_stats.count_subscribed = F('count_subscribed') - 1
            if instance.has_shopped:
                dine_stats.count_shopped = F('count_shopped') - 1
            if instance.has_cooked:
                dine_stats.count_cooked = F('count_cooked') - 1
            if instance.has_cleaned:
                dine_stats.count_cleaned = F('count_cleaned') - 1

        with transaction.atomic():
            instance.dining_list.refresh_from_db()
            instance.dining_list.diners = F('diners') - 1
            user_creds.credit = F('credit') + instance.dining_list.get_credit_cost()
            user_creds.save()
            dine_stats.save()
            instance.dining_list.save()

"""""""""""""""""""""""""""""""""""""""""""""""""""
Create a dining_detail entry when a new user signs up
"""""""""""""""""""""""""""""""""""""""""""""""""""

@receiver(post_save, sender=UserInformation)
@receiver(post_save, sender=User)
def create_user_dining_details(sender, instance=False, created=False,  **kwargs):
    """
    Create a new userDiningSettingsModel upon creation of a user model (note, not userinformation as it does not catch
    the manage.py createsuperuser)
    :param sender:
    :param instance: the created instance
    :param created: whether this instance was newly created
    :param kwargs: not used
    """
    if created:
        instance = UserInformation.objects.get(pk=instance.pk)
        UserDiningSettings(user=instance).save()
        UserDiningStats(user=instance).save()
