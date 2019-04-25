from django.apps import AppConfig


class UserDetailsConfig(AppConfig):
    name = 'UserDetails'

    def ready(self):
        # Import to register the receiver in this module
        import UserDetails.externalaccounts
