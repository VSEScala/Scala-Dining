from django.apps import AppConfig


class CreditmanagementConfig(AppConfig):
    name = 'CreditManagement'

    def ready(self):
        import CreditManagement.recievers