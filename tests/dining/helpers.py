from datetime import date

from Dining.models import DiningList
from UserDetails.models import Association


def create_dining_list(**kwargs):
    """
    Creates a dining list with default date and association if omitted.
    """
    if not 'association' in kwargs:
        kwargs['association'] = Association.objects.create()
    if not 'date' in kwargs:
        kwargs['date'] = date(2018,1,4)
    return DiningList.objects.create(**kwargs)
