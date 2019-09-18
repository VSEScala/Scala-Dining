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
- `pipenv shell`
- `python manage.py migrate`
- `python manage.py createsuperuser`

You don't need `pipenv shell` to set the environment, you can also use `pipenv
run`.

### Development commands

These assume that the environment is set correctly, e.g. using `pipenv shell`.

- Run test server: `python manage.py runserver`
- Run test suite: `python manage.py test`
- Lint code: `flake8`

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
