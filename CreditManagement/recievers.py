from django.db.models.signals import post_save
from django.dispatch import receiver
from CreditManagement.models import AssociationCredit, UserCredit
from django.conf import settings

from UserDetails.models import Association


"""""""""""""""""""""""""""""""""""""""""""""""""""
Spawn a new associationcredit when a new assocation is created
"""""""""""""""""""""""""""""""""""""""""""""""""""
@receiver(post_save, sender=Association)
def create_association_credit(sender, instance=False, created=False,  **kwargs):
    """
    Create a new Association_credit file when a new association is added
    :param sender:
    :param instance: The association instance
    :param created: Whether this association was created
    :param kwargs: not used
    """
    if created:
        AssociationCredit(association=instance).save()


"""""""""""""""""""""""""""""""""""""""""""""""""""
Create a dining_detail entry when a new user signs up
"""""""""""""""""""""""""""""""""""""""""""""""""""
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_dining_details(sender, instance, created, **kwargs):
    """
    Create a new userDiningSettingsModel upon creation of a user model (note, not userinformation as it does not catch
    the manage.py createsuperuser)
    :param sender:
    :param instance: the created instance
    :param created: whether this instance was newly created
    :param kwargs: not used
    """
    if created:
        UserCredit(user=instance).save()