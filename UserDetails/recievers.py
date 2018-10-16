from django.db.models.signals import post_save
from django.dispatch import receiver
from UserDetails.models import UserDetail, User, Association, AssociationDetails
from django.contrib.auth.models import User, Group


@receiver(post_save, sender=User)
@receiver(post_save, sender=User)
def create_use_details(sender, instance=False, created=False,  **kwargs):
    if created:
        instance = User.objects.get(pk=instance.pk)
        UserDetail(related_user=instance).save()



@receiver(post_save, sender=Group)
@receiver(post_save, sender=Association)
def create_association_details(sender, instance=False, created=False, **kwargs):
    if created:
        association = Association.objects.get(pk=instance.pk)
        AssociationDetails(association=association).save()
