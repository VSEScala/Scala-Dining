from django.apps import AppConfig


class UserDetailsConfig(AppConfig):
    name = "userdetails"

    def ready(self):
        # Import to register the receivers in this module
        # noinspection PyUnresolvedReferences
        import userdetails.externalaccounts  # noqa F401
