from django.apps import AppConfig


class UserDetailsConfig(AppConfig):
    name = 'UserDetails'

    def ready(self):
        import UserDetails.recievers