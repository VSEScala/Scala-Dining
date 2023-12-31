from django import template
from django.utils.formats import localize

register = template.Library()


@register.filter
def euro(value):
    """Format for euro values."""
    return f"-€{localize(-value)}" if value < 0 else f"€{localize(value)}"


@register.filter
def negate(value):
    """Negates given numeric value."""
    return -value
