"""Just some function to create a transactions CSV."""

import csv
from typing import Iterator

from django.db.models import QuerySet
from django.utils.timezone import localdate


class Echo:
    """An echoing writer."""

    def write(self, value):
        return value


def transactions_csv(transactions: QuerySet) -> Iterator:
    """Returns an iterator that yields the transaction CSV rows.

    Args:
        transactions: A QuerySet of transactions. Cannot be a list, because we will
            modify the query to fetch related fields.
    """
    # This speeds up the query by >100x
    transactions = transactions.select_related(
        "source",
        "target",
        "created_by",
        "source__user",
        "source__association",
        "target__user",
        "target__association",
    )

    writer = csv.writer(Echo())
    yield writer.writerow(
        [
            "Date (yyyy-mm-dd)",
            "Source account",
            "Destination account",
            "Source type",
            "Destination type",
            "Amount",
            "Description",
            "Created by",
        ]
    )

    get_account_type = lambda account: (
        "User" if account.user else "Association" if account.association else "Special"
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
