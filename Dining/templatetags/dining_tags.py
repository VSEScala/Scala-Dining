from django import template

from Dining.models import DiningEntry

register = template.Library()


@register.filter(name='can_join_slot')
def can_join_slot(slot, user):
    # Try creating an entry
    return slot.can_join(user)
    # ToDo: fix this code and anything else which is processed with the form
    from Dining.forms import DiningEntryUserCreateForm
    form = DiningEntryUserCreateForm(user, slot, data={})
    return form.is_valid()


@register.filter(name='is_on_slot')
def is_on_slot(slot, user):
    return slot.internal_dining_entries().filter(user=user).exists()


@register.filter(name='has_paid')
def has_paid(slot, user):
    try:
        entry = slot.internal_dining_entries().get(user=user)
        return entry.has_paid
    except DiningEntry.DoesNotExist:
        pass
    return False
