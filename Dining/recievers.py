from django.db.models.signals import post_save
from django.dispatch import receiver

from Dining.models import UserDiningSettings
from UserDetails.models import User


@receiver(post_save, sender=User)
def create_user_dining_details(sender, instance=False, created=False, **kwargs):
    """
    Create a new userDiningSettingsModel upon creation of a user model (note, not userinformation as it does not catch
    the manage.py createsuperuser)
    :param sender:
    :param instance: the created instance
    :param created: whether this instance was newly created
    :param kwargs: not used
    """
    if created:
        instance = User.objects.get(pk=instance.pk)
        UserDiningSettings(user=instance).save()
