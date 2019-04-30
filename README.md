# Scala-Dining-WebApp

Contains the Scala Dining Website Design

[![Build Status](https://travis-ci.com/DutcherNL/Scala-Dining-WebApp.svg?branch=master)](https://travis-ci.com/DutcherNL/Scala-Dining-WebApp)

## Prerequisites

- Python 3

## Main application

### First time set-up

This will install the project

- (Optional) create virtual environment
- `pip install -r requirements.txt`
- `./manage.py migrate`
- `./manage.py createsuperuser`

### Running the project

- `./manage.py runserver`

Now navigate to [localhost:8000](http://localhost:8000)

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

## Code coverage
To get a test coverage report:
* `pip install coverage`
* `coverage run manage.py test`
* Console report: `coverage report`
* HTML report: `coverage html`

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
