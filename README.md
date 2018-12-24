# Scala-Dining-WebApp
Contains the Scala Dining Website Design

## Prerequisites

- Python 3

## Main application

### First time set-up

This will install the project

- (Optional) create virtual environment
- `pip install -r requirements.txt`
- `./manage.py makemigrations`
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
            |          |
            V          V
CreditManagement --> UserDetails
```

## Code coverage
To get a test coverage report:
* `pip install coverage`
* `coverage run manage.py test`
* Console report: `coverage report`
* HTML report: `coverage html`

## Todo

* Make app names lowercase to conform to Python style guide ([PEP8](https://www.python.org/dev/peps/pep-0008/)).