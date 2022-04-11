# Scala Dining

Cooking website.

## Set-up

### Local Python

* Create and activate virtual environment
* Copy `.env.example` to `.env` and adjust as wanted
* `pip install -r requirements/common.txt -r requirements/dev.txt`

### Docker

- Install Docker and Docker Compose
- `docker-compose build`
- `docker-compose up`
- (`docker-compose exec app python manage.py migrate`)

## Development commands

* Lint code: `flake8`
* Run unit tests: `python manage.py test`
* Create superuser: `python manage.py createsuperuser`
* Development server: `python manage.py runserver`
* Apply migrations: `python manage.py migrate`

## On dependencies

To add a new dependency, append it to `requirements/common.in`, install `pip-tools`
inside the virtual environment
and run `pip-compile requirements/common.in`.
See [pip-tools documentation](https://github.com/jazzband/pip-tools)
for details.

Requirements only for development (e.g. linting) go in `requirements/dev.in`,
only for production (gunicorn) go in `requirements/prod.in`.