import decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum

from CreditManagement.models.transactions import Entry
from UserDetails.models import Association


class Account(models.Model):
    """An account is a collection of credit/debit statements.

    Each credit/debit statement is stored as an Entry instance. See the Entry
    model for details. See the Transaction model for general details about
    double-entry bookkeeping.
    """

    def balance(self) -> decimal.Decimal:
        """Calculates the account balance from all entries."""
        aggregate = Entry.objects.filter(account=self).aggregate(Sum('amount'))
        return aggregate['amount__sum']


class UserAccount(Account):
    """A credit account that is linked to a user."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, unique=True)

    @classmethod
    def get(cls, user):
        """Get user account via a user instance.

        The account will be created if it does not exist.
        """
        account, _ = cls.objects.get_or_create(user=user)
        return account


class AssociationAccount(Account):
    """A credit account that is linked to an association."""
    association = models.ForeignKey(Association, on_delete=models.PROTECT, unique=True)

    @classmethod
    def get(cls, association):
        """Get association account via the association instance."""
        account, _ = cls.objects.get_or_create(association=association)
        return account


SYSTEM_ACCOUNT = 'sy'
GENERAL_ACCOUNT_TYPES = ((SYSTEM_ACCOUNT, 'System owner'),)


class GeneralAccount(Account):
    """A general account for recording system in and out cash flow.

    In our system, we currently have one general account, dubbed the system
    account. This is the account that records the liabilities of the system
    owner, which in our case is the division in Scala that manages the kitchen
    cost payments. The balance of this account indicates what the system owner
    owes to others or should still receive from others. A positive balance
    indicates that Scala (system owner) still owes in total money from other
    users and/or associations.

    Balance example: when a user signs up for a dining list, the money is
    transferred from the user account to the general system account. The user
    account has a balance of -50 cents which indicates a debt. In this case the
    debt is to the system owner which is indicated by the +50 cents balance of
    the system account. When the user upgrades his balance by handing over
    money to an association, that association creates a transaction which makes
    the user balance positive and the association balance negative, indicating
    that now the association owes money to Scala. When the association pays the
    system owner Scala, this payment is balanced in the system by creating a
    reversing transaction in the system from Scala to the association.
    """
    type = models.CharField(max_length=2, choices=GENERAL_ACCOUNT_TYPES, unique=True)

    @classmethod
    def get(cls, account_type: str = SYSTEM_ACCOUNT):
        """Get the account of given type, by default the system account."""
        account, _ = cls.objects.get_or_create(type=account_type)
        return account
