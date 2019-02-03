from django.apps import AppConfig


class CreditManagementConfig(AppConfig):
    name = 'CreditManagement'

    def ready(self):
        import CreditManagement.recievers