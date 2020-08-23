from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from dining.models import UserDiningSettings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_dining_details(sender, instance=False, created=False, **kwargs):
    """Creates a new UserDiningSettings instance upon creation of a user.

    (Note, not userinformation as it does not catch the manage.py createsuperuser.)
    """
    if created:
        UserDiningSettings.objects.create(user=instance)
