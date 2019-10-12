from django.apps import AppConfig


class UserDetailsConfig(AppConfig):
    name = 'UserDetails'

    def ready(self):
        # Import to register the receiver in this module
        # noinspection PyUnresolvedReferences
        import UserDetails.externalaccounts  # noqa: F401
