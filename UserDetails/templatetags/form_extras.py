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


@register.filter(name='can_join_slot')
def can_join_slot(slot, user):
    return slot.can_join(user)


@register.filter(name='is_on_slot')
def is_on_slot(slot, user):
    return slot.internal_dining_entries().filter(user=user).exists()


@register.filter(name='has_paid')
def has_paid(slot, user):
    entry = slot.internal_dining_entries().get(user=user)
    if entry is not None:
        return entry.has_paid
    return False

