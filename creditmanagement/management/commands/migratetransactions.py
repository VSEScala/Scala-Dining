from django.core.management import BaseCommand
from django.db import transaction

from creditmanagement.models import Transaction, PendingTransaction, FixedTransaction, Account
from userdetails.models import User


class Command(BaseCommand):
    help = ("Migrates the transactions from old version to new version. "
            "The command createaccounts needs to be run first otherwise this will fail.")

    def handle(self, *args, **options):  # noqa: C901
        # Sanity checks

        # New transactions table must be empty!
        if Transaction.objects.exists():
            self.stderr.write("Transactions table is not empty, aborted")
            return

        # Check that there are no pending transactions
        if PendingTransaction.objects.exists():
            self.stderr.write("PendingTransaction table is not empty, aborted")
            return

        # Note that the PendingDiningListTracker table has already been removed in a migration, but in that migration
        # it is checked whether the table was empty.

        # Create a user account to use for created_by
        import_user, created = User.objects.get_or_create(username='imported_transactions_creator',
                                                          email='invalid@localhost')
        import_user.first_name = "Unknown"
        import_user.save()

        # Create new transactions from the FixedTransaction table
        transactions = []
        kitchen_cost_account = Account.objects.get(special='kitchen_cost')
        generic_account = Account.objects.get(special='generic')
        for t in FixedTransaction.objects.all():
            # Integrity checks
            if (t.source_user and t.source_association) or (t.target_user and t.target_association):
                raise ValueError("Invalid transaction in database")
            if not t.confirm_moment:
                raise ValueError("Invalid transaction: no confirm moment")

                # Get source account
            if t.source_user:
                source = t.source_user.account
            elif t.source_association:
                source = t.source_association.account
            else:
                source = generic_account

            # Get target account
            if t.target_user:
                target = t.target_user.account
            elif t.target_association:
                target = t.target_association.account
            else:
                target = kitchen_cost_account

            tx = Transaction(source=source,
                             target=target,
                             amount=t.amount,
                             moment=t.order_moment,
                             description=t.description or '-',
                             created_by=import_user)
            transactions.append(tx)

        # Print changes that will be applied and ask for confirmation
        for tx in transactions:
            s = "Transaction({}, {}, {}, {}, {})".format(tx.source, tx.target, tx.amount, tx.moment, tx.description)
            self.stdout.write(s)
        self.stdout.write("The transactions listed above will be created.")
        y = input("Proceed? [y/N] ")
        if y != 'y':
            return

        # Apply
        with transaction.atomic():
            for tx in transactions:
                tx.save()
