from django import template

from Dining.models import DiningEntry

register = template.Library()


@register.filter
def can_join(dining_list, user):
    # Try creating an entry
    return dining_list.can_add_diners(user, check_for_self=True)


@register.filter
def can_add_others(dining_list, user):
    """Exhaustive test (for correctness) is not needed since it's only for view usage"""
    is_adjustable = dining_list.is_adjustable()
    is_owner = dining_list.is_authorised_user(user)
    has_room = dining_list.is_open() and dining_list.has_room()
    limited = dining_list.limit_signups_to_association_only and not user.usermembership_set.filter(
        association=dining_list.association).exists()
    return is_adjustable and (is_owner or (has_room and not limited))


@register.filter
def has_joined(dining_list, user):
    return dining_list.internal_dining_entries().filter(user=user).exists()


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
