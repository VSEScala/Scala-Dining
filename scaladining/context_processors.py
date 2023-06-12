from django.conf import settings


def scala(request):
    """Adds some variables to every template context."""
    return {
        "MINIMUM_BALANCE_FOR_DINING_SIGN_UP": settings.MINIMUM_BALANCE_FOR_DINING_SIGN_UP
    }
