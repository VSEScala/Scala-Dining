# Credit management


### Implementation notes

* Transactions are decoupled from entity types, the user and association fields
  are removed and replaced with a general Account model. This decoupling makes
  it possible to have various different account types.
* Minimum balance validation happens while the credit account is locked. This
  fixes the race condition that was still present which made it possible to
  circumvent the minimum balance check.
* The models are implemented using a double-entry bookkeeping system, see
  Wikipedia and the various Django examples found via Google. This makes it
  much easier to calculate the balance for an account, since there are no
  source and target columns. To ensure integrity, a database constraint is
  needed to make sure that all transaction entries add up to zero.
* We have an enumeration of special accounts for transactions like kitchen cost
  payments. The target for e.g. the kitchen cost payment would be a kitchen
  cost special account. This makes it possible to get reportings on these
  different types of accounts, e.g. it's possible to get a sum of all kitchen
  costs, or for only a certain period, by aggregating the rows for the kitchen
  cost account.
* Using the 'cash book' account we can directly find how much money is 'in the
  system'.
* I've thought a lot about performance considerations for calculating the
  balance. It is probably not going to be an issue that all entries need to be
  summed each time to calculate the balance, as that's a very fast operation.
  The couple of Django projects that I analyzed all calculated the balance each
  time from all entries. However, if we encounter performance issues, there are
  a couple of solutions that we can implement. See the RobertKhou link or the
  StackOverflow link about derived balance.



### Used resources

Very very good article:
https://medium.com/@RobertKhou/double-entry-accounting-in-a-relational-database-2b7838a5d7f8

Wikipedia: https://en.wikipedia.org/wiki/Double-entry_bookkeeping_system

Inspiration:

* https://github.com/SwingTix/bookkeeper/blob/master/swingtix/bookkeeper/models.py
* https://github.com/kunkku/django-financial-accounting/blob/master/accounting/models.py
* https://github.com/adamcharnock/django-hordak/blob/master/hordak/models/core.py

Inspiration for the locking:
https://medium.com/@hakibenita/bullet-proofing-django-models-c080739be4e

Stack overflow:

* Database design for double entry accounting system: https://stackoverflow.com/q/2494343/2373688
* Derived account balance: https://stackoverflow.com/q/29688982/2373688
* Account software design patterns: https://stackoverflow.com/q/163517/2373688


### Transfer

This outlines the transfer from the original setup to the new models.

*Note: obviously before each potentially destructive step always perform a
backup first.*

* All pending transactions need to be finalized manually before the transfer.
* The finalized transactions are converted to the new system using a migration
file. The migration is one way, there's no undo migration. The transactions are
then stored twice, for both the old and new system.
* After manually checking that all transactions are transferred correctly, the
old tables can be removed using another migration.




### Transaction archival


It is possible to archive transactions when this is needed.
However this is not implemented as it should never be necessary.
When this appears to be necessary, it can be done using a procedure which replaces a set of transactions
with a summary transaction that has the same net amount as for the transaction set.
The transaction set should not be discarded but instead it should be moved to an archival table.

