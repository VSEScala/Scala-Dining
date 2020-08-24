from django.db import connection
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver

from creditmanagement.models import Account
from userdetails.models import User, Association


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
    for name, label in Account.SPECIAL_ACCOUNTS:
        Account.objects.get_or_create(special=name)


@receiver(post_migrate)
def cleanup_old_views(sender, **kwargs):
    """This cleans up the old view for UserCredit.

    This function can be removed once it has run at least once on the live database.
    """
    # Views that need to be removed
    to_drop = ['creditmanagement_usercredit']
    with connection.cursor() as cursor:
        for v in to_drop:
            cursor.execute('DROP VIEW IF EXISTS {}'.format(v))
