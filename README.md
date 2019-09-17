# Scala-Dining-WebApp

Contains the Scala Dining Website Design

[![Build Status](https://travis-ci.com/DutcherNL/Scala-Dining-WebApp.svg?branch=master)](https://travis-ci.com/DutcherNL/Scala-Dining-WebApp)

## Prerequisites

- Python 3
- Pipenv, not strictly necessary. If not installed, you'll need to install the
dependencies in `Pipfile` manually.

## Main application

### First time set-up

- `pipenv install --dev`
- `pipenv run python manage.py migrate`
- `pipenv run python manage.py createsuperuser`

Alternatively you can set the environment correctly using `pipenv shell` so
that you can directly call `python manage.py`.

### Development commands

- Run test server: `pipenv run python manage.py runserver`
- Lint code: `pipenv run lint`
- Run test suite: `pipenv run test`

## App dependency graph
The code is currently not adhering to this dependency graph, but it would be
nice to work towards it. The code is easier to understand and thus maintain
when it adheres to a graph like this one.

```
         Dining --------
            ^          |
            |          V
CreditManagement --> UserDetails
```

## Deployment

The table `CreditManagement_fixedtransaction` needs to be insert-only for the database user that is used by the application.

```sql
-- Needs to be executed as superuser, e.g. postgres. Replace scala by the database user

-- Grant select and insert on CreditManagement_fixedtransaction
REVOKE ALL ON TABLE "CreditManagement_fixedtransaction" FROM scala;
ALTER TABLE "CreditManagement_fixedtransaction" OWNER TO postgres;
GRANT SELECT, INSERT ON TABLE "CreditManagement_fixedtransaction" TO scala;

-- Grant usage on CreditManagement_fixedtransaction_id_seq
REVOKE ALL ON SEQUENCE "CreditManagement_fixedtransaction_id_seq" FROM scala;
ALTER SEQUENCE "CreditManagement_fixedtransaction_id_seq" OWNER TO postgres;
GRANT USAGE ON SEQUENCE "CreditManagement_fixedtransaction_id_seq" TO scala;
```

Static and media files are served with a cache directive of 10 minutes.
