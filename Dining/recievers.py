from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from Dining.models import UserDiningSettings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_dining_details(sender, instance=False, created=False, **kwargs):
    """
    Create a new userDiningSettingsModel upon creation of a user model (note, not userinformation as it does not catch
    the manage.py createsuperuser)
    """
    if created:
        UserDiningSettings.objects.create(user=instance)
