# Scala Dining

Cooking website.

## Set-up

### Local Python

- Create and activate an virtual environment
- Copy `.env.example` to `.env` and adjust as wanted
- `pip install -r requirements.txt -r dev-requirements.txt`
- `python manage.py runserver`
- (`python manage.py migrate`)

### Docker

- Install Docker and Docker Compose
- `docker-compose build`
- `docker-compose up`
- (`docker-compose exec app python manage.py migrate`)

## Development commands

- Lint code: `flake8`
- Run unit tests: `python manage.py test`
- Create superuser: `python manage.py createsuperuser`

## On dependencies

To add a new dependency, append it to `requirements.in`, install `pip-tools`
inside the virtual environment
and run `pip-compile requirements.in`.
See [pip-tools documentation](https://github.com/jazzband/pip-tools)
for details.
