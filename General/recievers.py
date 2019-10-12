from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PageVisitTracker


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_dining_details(sender, instance=False, created=False, **kwargs):
    if created:
        PageVisitTracker.get_latest_visit('rules', instance, update=True)
        PageVisitTracker.get_latest_visit('updates', instance, update=True)
