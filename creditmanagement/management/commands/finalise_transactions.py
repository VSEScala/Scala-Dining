from django.core.management.base import BaseCommand

from creditmanagement.models import AbstractPendingTransaction


class Command(BaseCommand):
    help = 'Finalises all expired transactions'

    def handle(self, *args, **options):
        results = AbstractPendingTransaction.finalise_all_expired()
        for transaction in results:
            self.stdout.write(self.style.SUCCESS('Successfully finalised "%s"' % transaction))
