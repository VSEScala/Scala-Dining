from django.apps import AppConfig


class DiningConfig(AppConfig):
    name = 'Dining'

    def ready(self):
        # noinspection PyUnresolvedReferences
        import Dining.recievers  # noqa: F401
