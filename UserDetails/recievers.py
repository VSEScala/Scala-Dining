from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import post_save
from django.dispatch import receiver

from UserDetails.models import UserDetail, Association, AssociationDetails


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_details(sender, instance=False, created=False,  **kwargs):
    if created:
        UserDetail.objects.create(related_user=instance)


@receiver(post_save, sender=Group)
@receiver(post_save, sender=Association)
def create_association_details(sender, instance=False, created=False, **kwargs):
    if created:
        AssociationDetails.objects.create(association=instance)
