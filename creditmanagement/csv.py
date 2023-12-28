"""Just some function to create a transactions CSV."""
import csv
from typing import Iterator

from django.utils.timezone import localdate


class Echo:
    """An echoing writer."""

    def write(self, value):
        return value


def transactions_csv(transactions) -> Iterator:
    """Returns an iterator that yields the transaction CSV rows.

    Args:
        transactions: List or QuerySet of transactions.
    """
    writer = csv.writer(Echo())
    yield writer.writerow(
        [
            "Date (yyyy-mm-dd)",
            "Debtor name",
            "Creditor name",
            "Debtor type",
            "Creditor type",
            "Amount",
            "Description",
            "Created by",
        ]
    )

    get_account_type = (
        lambda account: "User"
        if account.user
        else "Association"
        if account.association
        else "Special"
    )

    for t in transactions:
        yield writer.writerow(
            [
                localdate(t.moment).isoformat(),  # In our timezone (Europe/Amsterdam)
                str(t.source),
                str(t.target),
                get_account_type(t.source),
                get_account_type(t.target),
                t.amount,
                t.description,
                str(t.created_by),
            ]
        )
