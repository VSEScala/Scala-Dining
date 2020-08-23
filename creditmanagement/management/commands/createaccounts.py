from django.core.management import BaseCommand

from creditmanagement.models import Account
from userdetails.models import User, Association


class Command(BaseCommand):
    help = "Creates missing credit accounts for users and associations."

    def handle(self, *args, **options):
        for u in User.objects.all():
            try:
                u.account
            except Account.DoesNotExist:
                Account.objects.create(user=u)
                self.stdout.write("Created account for {}".format(u))
        for a in Association.objects.all():
            try:
                a.account
            except Account.DoesNotExist:
                Account.objects.create(association=a)
                self.stdout.write("Created account for {}".format(a))
