from django import template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def euro(value):
    """Format for euro values."""
    v = "{}&euro;{}".format('-' if value < 0 else '', intcomma(abs(value)))
    return mark_safe(v)
