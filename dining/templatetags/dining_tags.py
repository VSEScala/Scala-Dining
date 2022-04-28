from django import template

from dining.forms import DiningEntryInternalCreateForm, DiningEntryDeleteForm
from dining.models import DiningEntry, DiningList, DiningCommentVisitTracker

register = template.Library()


@register.filter
def can_join(dining_list, user):
    # Try creating an entry
    entry = DiningEntry(dining_list=dining_list, created_by=user)
    form = DiningEntryInternalCreateForm({'user': str(user.pk)}, instance=entry)
    return form.is_valid()


@register.filter
def cant_join_reason(dining_list, user):
    """Returns the reason why someone can't join (raises exception when they can join)."""
    entry = DiningEntry(dining_list=dining_list, created_by=user)
    form = DiningEntryInternalCreateForm({'user': str(user.pk)}, instance=entry)
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
    limited = dining_list.limit_signups_to_association_only and not user.usermembership_set.filter(
        association=dining_list.association).exists()
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
    return DiningEntry.objects.internal().filter(dining_list=dining_list, user=user).first()


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
def comments_total(dining_list: DiningList) -> int:
    return dining_list.diningcomment_set.count()


@register.filter
def comments_unread(dining_list: DiningList, user) -> int:
    # Get the amount of unread messages
    view_time = DiningCommentVisitTracker.get_latest_visit(user=user, dining_list=dining_list)
    if view_time is None:
        return dining_list.diningcomment_set.count()
    else:
        return dining_list.diningcomment_set.filter(timestamp__gte=view_time).count()
