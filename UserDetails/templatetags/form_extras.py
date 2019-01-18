from django import template

from Dining.models import DiningEntry

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


# Todo: depends on Dining app
@register.filter(name='can_join_slot')
def can_join_slot(slot, user):
    # Try creating an entry
    from Dining.forms import DiningEntryCreateForm
    form = DiningEntryCreateForm(user, slot, data={})
    return form.is_valid()


# Todo: depends on Dining app
@register.filter(name='is_on_slot')
def is_on_slot(slot, user):
    return slot.internal_dining_entries().filter(user=user).exists()


# Todo: depends on Dining app
@register.filter(name='has_paid')
def has_paid(slot, user):
    try:
        entry = slot.internal_dining_entries().get(user=user)
        return entry.has_paid
    except DiningEntry.DoesNotExist:
        pass
    return False

