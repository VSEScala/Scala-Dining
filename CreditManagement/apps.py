from django.apps import AppConfig


class CreditManagementConfig(AppConfig):
    name = 'CreditManagement'

    def ready(self):
        # noinspection PyUnresolvedReferences
        import CreditManagement.recievers  # noqa: F401
