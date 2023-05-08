"""This migration unfolds the cancelled column into separate transaction rows.

The backward function is a noop. It does not reconstruct the cancelled column.

For sanity check, we compare all balances before and after the migration to
make sure they have not changed.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import migrations
from django.db.models import Sum


def compute_balance(Account, Transaction):
    """Computes the balance for all accounts and returns a list."""
    qs = Transaction.objects.filter(cancelled=None)
    return [
        (qs.filter(target=a).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00'))
        - (qs.filter(source=a).aggregate(sum=Sum('amount'))['sum'] or Decimal('0.00'))
        for a in Account.objects.order_by('id')
    ]


def forward(apps, schema_editor):
    Account = apps.get_model("creditmanagement", "Account")
    Transaction = apps.get_model("creditmanagement", "Transaction")

    if Transaction.objects.count() == 0:
        # This migration caused the test cases that used fixtures to fail,
        # because we create a new user below. This created user collides with
        # the users that are being created from fixtures.
        #
        # To prevent this, when there are no transactions, we skip this
        # migration so that the user is not created.
        return

    # Sanity check: compare balances before and after
    before = compute_balance(Account, Transaction)

    # We create a dedicated user for the reversal transactions, so that we can
    # easily find them if something went wrong.
    User = apps.get_model("userdetails", "User")
    try:
        u = User.objects.get(email="invalid2@localhost")
    except User.DoesNotExist:
        u = User.objects.create(
            username="transaction_cancel_migration_user",
            email="invalid2@localhost",
            first_name="Transaction Cancel Migration User"
        )

    for tx in Transaction.objects.exclude(cancelled=None):
        # Manually create reversal transaction (we cannot use the reversal()
        # method).
        Transaction.objects.create(
            source=tx.target,
            target=tx.source,
            amount=tx.amount,
            moment=tx.moment + timedelta(seconds=1),  # If the moment was exactly equal, ordering might go wrong
            description=f'Refund "{tx.description}"',
            created_by=u,
        )
        # We need to clear out the cancel column values, because otherwise if
        # the migration runs twice for some reason, the cancel transactions
        # will be duplicated.
        tx.cancelled = None
        tx.cancelled_by = None
        tx.save()

    after = compute_balance(Account, Transaction)
    if before != after:
        raise ValueError("Transaction migration sanity check failed")


class Migration(migrations.Migration):
    dependencies = [
        ('creditmanagement', '0015_auto_20220428_2113'),
    ]

    operations = [
        migrations.RunPython(forward, reverse_code=migrations.RunPython.noop, elidable=True)
    ]
