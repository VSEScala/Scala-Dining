from django.apps import AppConfig


class DiningConfig(AppConfig):
    name = "dining"

    def ready(self):
        # Put receivers here
        pass
