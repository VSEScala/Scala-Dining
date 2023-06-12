from django.db import DatabaseError
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from creditmanagement.models import Account
from userdetails.models import Association, User


@receiver(post_save, sender=User)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(user=instance)


@receiver(post_save, sender=Association)
def create_association_account(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(association=instance)


@receiver(post_migrate)
def create_special_accounts(sender, **kwargs):
    """Ensures that the special bookkeeping accounts exist."""
    try:
        for name, label in Account.SPECIAL_ACCOUNTS:
            Account.objects.get_or_create(special=name)
    except DatabaseError:
        # Database error might arise when migrating backwards
        print("Failed to create special accounts")
