from django.apps import AppConfig


class UserDetailsConfig(AppConfig):
    name = 'userdetails'

    def ready(self):
        # Import to register the receiver in this module
        import userdetails.externalaccounts
