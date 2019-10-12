from django import template

register = template.Library()


@register.filter(name='css')
def addcss(field, css):
    return field.as_widget(attrs={"class": css})


@register.filter(name='multiply')
def multiply(var, multiply_value):
    return var * multiply_value


@register.filter(name='get_class')
def get_class(value):
    return value.__class__.__name__
