from django.conf import settings


def scala(request):
    """Adds some variables to every template context."""
    return {
        "SITE_BANNER": settings.SITE_BANNER,
        "MINIMUM_BALANCE_FOR_DINING_SIGN_UP": settings.MINIMUM_BALANCE_FOR_DINING_SIGN_UP,
    }
