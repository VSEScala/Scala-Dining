from django import template
from django.conf import settings
from django.utils import timezone

from Dining.forms import DiningEntryUserCreateForm, DiningEntryDeleteForm, CreateSlotForm
from Dining.models import DiningEntry, DiningEntryUser, DiningList

register = template.Library()


@register.filter
def can_join(dining_list, user):
    # Try creating an entry
    entry = DiningEntryUser(dining_list=dining_list, created_by=user)
    form = DiningEntryUserCreateForm({'user': str(user.pk)}, instance=entry)
    return form.is_valid()


@register.filter
def cant_join_reason(dining_list, user):
    """Returns the reason why someone can't join (raises exception when she can join)"""
    entry = DiningEntryUser(dining_list=dining_list, created_by=user)
    form = DiningEntryUserCreateForm({'user': str(user.pk)}, instance=entry)
    return form.non_field_errors()[0]


@register.filter
def can_add_others(dining_list, user):
    """Exhaustive test (for correctness) is not needed since it's only for view usage"""
    is_adjustable = dining_list.is_adjustable()
    is_owner = dining_list.is_owner(user)
    has_room = dining_list.is_open() and dining_list.has_room()
    limited = dining_list.limit_signups_to_association_only and not user.usermembership_set.filter(
        association=dining_list.association).exists()
    return is_adjustable and (is_owner or (has_room and not limited))


@register.filter
def has_joined(dining_list, user):
    return dining_list.internal_dining_entries().filter(user=user).exists()


@register.filter
def can_delete_entry(entry, user):
    """Whether given user can delete the entry"""
    return DiningEntryDeleteForm(entry, user, {}).is_valid()


@register.filter
def get_entry(dining_list, user):
    """Get user entry (not external) for given user"""
    return DiningEntryUser.objects.filter(dining_list=dining_list, user=user).first()


@register.filter
def has_paid(dining_list, user):
    try:
        entry = dining_list.internal_dining_entries().get(user=user)
        return entry.has_paid
    except DiningEntry.DoesNotExist:
        pass
    return False


@register.filter
def paid_count(dining_list):
    """Number of people who have paid for given list"""
    return DiningEntry.objects.filter(dining_list=dining_list, has_paid=True).count()


@register.filter
def is_owner(dining_list, user):
    return dining_list.is_owner(user)


@register.filter
def cant_create_dining_list_reason(user, date):
    """Returns None if the user can create a dining list, else it returns the reason why not"""

    # Copied from the view, could also do a fake form is_valid check and return the error message when not valid
    # In the past
    if date < timezone.now().date():
        return "date is in the past"
    if date == timezone.now().date() and settings.DINING_SLOT_CLAIM_CLOSURE_TIME < timezone.now().time():
        return "too late to create a dining list today"

    # Slots available
    if DiningList.objects.available_slots(date) <= 0:
        return "no slots available"

    # User owns a dining list
    if DiningList.objects.filter(date=date, owners=user).exists():
        return "you already have a dining list for this day"

    return None
