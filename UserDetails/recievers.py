from django.db.models.signals import post_save
from django.dispatch import receiver
from UserDetails.models import UserDetail, Association, AssociationDetails
from django.contrib.auth.models import Group
from django.conf import settings


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_use_details(sender, instance=False, created=False,  **kwargs):
    if created:
        UserDetail(related_user=instance).save()



@receiver(post_save, sender=Group)
@receiver(post_save, sender=Association)
def create_association_details(sender, instance=False, created=False, **kwargs):
    if created:
        association = Association.objects.get(pk=instance.pk)
        AssociationDetails(association=association).save()
