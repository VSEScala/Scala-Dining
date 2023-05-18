import datetime
from typing import Optional

from django import template
from django.conf import settings
from django.utils import timezone

from dining.forms import DiningEntryDeleteForm, DiningEntryInternalForm
from dining.models import DiningEntry, DiningList
from userdetails.models import User

register = template.Library()


@register.filter
def can_join(dining_list, user):
    # Try creating an entry
    entry = DiningEntry(dining_list=dining_list, created_by=user)
    form = DiningEntryInternalForm({"user": str(user.pk)}, instance=entry)
    return form.is_valid()


@register.filter
def cant_join_reason(dining_list, user):
    """Returns the reason why someone can't join (raises exception when they can join)."""
    entry = DiningEntry(dining_list=dining_list, created_by=user)
    form = DiningEntryInternalForm({"user": str(user.pk)}, instance=entry)
    return form.non_field_errors()[0]


@register.filter
def can_add_others(dining_list, user):
    """Whether a user can add others on a dining list.

    This is not thoroughly tested for correctness, but that is not needed since
    it's only for view usage.
    """
    is_adjustable = dining_list.is_adjustable()
    is_owner = dining_list.is_owner(user)
    has_room = dining_list.is_open() and dining_list.has_room()
    limited = (
        dining_list.limit_signups_to_association_only
        and not user.usermembership_set.filter(
            association=dining_list.association
        ).exists()
    )
    return is_adjustable and (is_owner or (has_room and not limited))


@register.filter
def has_joined(dining_list, user):
    return dining_list.internal_dining_entries().filter(user=user).exists()


@register.filter
def can_delete_entry(entry, user):
    """Returns whether given user can delete the entry."""
    return DiningEntryDeleteForm(entry, user, {}).is_valid()


@register.filter
def get_entry(dining_list, user):
    """Gets the user entry (not external) for given user."""
    return (
        DiningEntry.objects.internal()
        .filter(dining_list=dining_list, user=user)
        .first()
    )


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
    """Returns the number of people who have paid for given list."""
    return DiningEntry.objects.filter(dining_list=dining_list, has_paid=True).count()


@register.filter
def is_owner(dining_list, user):
    return dining_list.is_owner(user)


@register.filter
def dining_list_creation_open(date: datetime.date) -> bool:
    """Returns whether dining list creation is open for given date.

    The date must be in the future or time must be before closure time for
    dining list creation to be open. Note that this doesn't mean that it's
    possible to create a dining list, there might be other reasons why that is
    still not possible.
    """
    if date < timezone.now().date():
        return False
    if (
        date == timezone.now().date()
        and settings.DINING_SLOT_CLAIM_CLOSURE_TIME < timezone.now().time()
    ):
        # Too late for today
        return False
    return True


@register.filter
def can_create_dining_list(user: User, date: datetime.date) -> bool:
    """Returns whether the user can create a dining list on the given date."""
    cant_create = cant_create_dining_list_reason(user, date)
    return dining_list_creation_open(date) and cant_create is None


@register.filter
def cant_create_dining_list_reason(user: User, date: datetime.date) -> Optional[str]:
    """Returns why the user can't create a dining list.

    When there is no reason found why a user can't create a dining list, the
    function will return None. This doesn't check whether dining list creation
    is open.
    """
    # Slots available
    if DiningList.objects.available_slots(date) <= 0:
        return "no slots available"

    # User owns a dining list
    if DiningList.objects.filter(date=date, owners=user).exists():
        return "you already have a dining list for this day"

    return None


@register.filter
def short_owners_string(dining_list: DiningList) -> str:
    """Returns the names of all owners for display in short form.

    For a larger number of owners, only the first name will be included.

    Returns:
        Names of the owners separated by ',' and 'and'
    """
    owners = list(dining_list.owners.all())

    if len(owners) > 1:
        first_names = [o.first_name for o in owners]
        # Join by comma and 'and'
        return "{} and {}".format(", ".join(first_names[:-1]), first_names[-1])
    elif len(owners) == 1:
        return owners[0].get_full_name()
    else:
        return ""
