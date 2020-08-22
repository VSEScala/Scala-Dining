from django.apps import AppConfig


class CreditManagementConfig(AppConfig):
    name = 'creditmanagement'

    def ready(self):
        import creditmanagement.recievers