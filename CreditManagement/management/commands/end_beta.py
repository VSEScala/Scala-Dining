from django.core.management.base import BaseCommand
from CreditManagement.models import FixedTransaction
from Dining.models import DiningList, DiningEntry, DiningEntryExternal

class Command(BaseCommand):
    help = 'Finalises all expired transactions'

    def handle(self, *args, **options):
        FixedTransaction.objects.all().delete()
        DiningList.objects.all().delete()
        DiningEntry.objects.all().delete()
        DiningEntryExternal.objects.all().delete()