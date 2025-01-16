# Scala Dining

🍲🥗🍣

## Get started with Docker

If you have Docker installed, you can run the app with the following command:

```bash
docker compose up --watch
```

When it's running, migrate the database and create a superuser:

```bash
docker compose exec app python manage.py migrate
docker compose exec app python manage.py createsuperuser
```


## Development commands

These commands require a local Python environment with the dependencies from 
`requirements.txt` and `dev-requirements.txt` installed.

* Lint code: `flake8`
* Blacken the code: `black .`
* Sort the imports: `isort --ac .`
* Run unit tests: `python manage.py test`
* Coverage: `coverage run manage.py test`
  * Command line report: `coverage report`
  * Generate HTML report: `coverage html`


## Dependencies

To add a new dependency, append it to `requirements.in`, install `pip-tools`
inside the virtual environment
and run `pip-compile requirements.in`.
See [pip-tools documentation](https://github.com/jazzband/pip-tools)
for details.

## Code style

The linter Flake8 expects the code, including docstrings, to follow the
[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
See the file `.flake8` for the exact configuration.

To let PyCharm use the correct docstring format, change the setting at
"Tools -> Python Integrated Tools -> Docstrings -> Docstring format" to Google.
