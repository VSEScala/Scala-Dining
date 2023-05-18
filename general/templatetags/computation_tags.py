from django import template

register = template.Library()


@register.filter
def subtract(value, arg):
    return value - arg


@register.filter
def minimum(value, arg):
    return min(value, arg)


@register.filter
def maximum(value, arg):
    return min(value, arg)
