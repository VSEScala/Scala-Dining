# PR

This PR rewrites the transaction handling.

## Purpose

- Reduce complexity and LOC.
- Get rid of database view to fix migrations errors and enable squashing of migrations.

## Migration

The database needs to be migrated for the new transactions table.
The following steps are necessary:

* Create `Account` instances for all users and associations.
* Finalize all pending transactions.
* Ensure `PendingDiningListTracker` table is empty.
* Copy over all transactions to the new table.