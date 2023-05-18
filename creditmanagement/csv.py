"""Just some function to create a transactions CSV."""
import csv
from typing import Iterable

from django.utils.timezone import get_default_timezone

from creditmanagement.models import Account, Transaction


def write_transactions_csv(
    csv_file, transactions: Iterable[Transaction], account_self: Account
):
    """Writes a transactions CSV file to the given file object.

    Args:
        csv_file: Can be any file-like object with a write() method.
        transactions: List or QuerySet of transactions.
        account_self: The account that is used to determine the direction. The
            opposite account is used for the (counterpart) name column.
    """
    csv_writer = csv.writer(csv_file)
    csv_writer.writerow(
        [
            "date",
            "direction",
            "account_type",
            "name",
            "email",
            "amount",
            "description",
            "created_by",
        ]
    )

    for t in transactions:
        # Determine direction and counterparty
        if t.source == account_self:
            direction = "out"
            counterparty = t.target
        elif t.target == account_self:
            direction = "in"
            counterparty = t.source
        else:
            raise ValueError("Transaction does not involve account_self")

        # Set timezone to ours (Europe/Amsterdam) and get rid of microseconds
        date = (
            t.moment.astimezone(get_default_timezone())
            .replace(microsecond=0)
            .isoformat()
        )
        account_type = (
            "user"
            if counterparty.user
            else "association"
            if counterparty.association
            else "special"
        )
        name = str(counterparty)
        email = counterparty.user.email if account_type == "user" else ""

        csv_writer.writerow(
            [
                date,
                direction,
                account_type,
                name,
                email,
                t.amount,
                t.description,
                str(t.created_by),
            ]
        )
