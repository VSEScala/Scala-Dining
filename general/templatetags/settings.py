from django import template
from django.conf import settings

register = template.Library()

ALLOWABLE_VALUES = ("BASE_URL",)


@register.simple_tag
def settings_value(name):
    if name in ALLOWABLE_VALUES:
        return getattr(settings, name, "")
    return ""
