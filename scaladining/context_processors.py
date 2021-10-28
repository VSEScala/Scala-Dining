from django.conf import settings


def dining(request):
    """Adds some variables to every template context."""
    return {
        'MINIMUM_BALANCE_FOR_DINING_SIGN_UP': settings.MINIMUM_BALANCE_FOR_DINING_SIGN_UP,
        'SITE_NOTICE': settings.SITE_NOTICE,
        'BREADCRUMB_NAV': settings.BREADCRUMB_NAV,
    }
