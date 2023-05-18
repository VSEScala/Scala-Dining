from django.apps import AppConfig


class CreditManagementConfig(AppConfig):
    name = "creditmanagement"

    def ready(self):
        # noinspection PyUnresolvedReferences
        import creditmanagement.receivers  # noqa: F401
