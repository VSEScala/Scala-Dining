from django.apps import AppConfig


class DiningConfig(AppConfig):
    name = 'Dining'

    def ready(self):
        import Dining.recievers