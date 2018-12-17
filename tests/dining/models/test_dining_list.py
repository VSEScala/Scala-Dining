from datetime import datetime, date, timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from Dining.models import DiningList, DiningEntry
from UserDetails.models import User

from django.db.models import QuerySet

class DiningListTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        pass

    def test_is_open(self):
        list = DiningList.objects.create(date=date(2015, 1, 1),
                                         sign_up_deadline=datetime(2015, 1, 1, 17, 00, tzinfo=timezone.utc))

        with patch.object(timezone, 'now', return_value=datetime(2015, 1, 1, 16, 59, tzinfo=timezone.utc)) as mock_now:
            self.assertTrue(list.is_open())
        with patch.object(timezone, 'now', return_value=datetime(2015, 1, 1, 17, 00, tzinfo=timezone.utc)) as mock_now:
            self.assertFalse(list.is_open())
        with patch.object(timezone, 'now', return_value=datetime(2015, 1, 1, 17, 1, tzinfo=timezone.utc)) as mock_now:
            self.assertFalse(list.is_open())

    def test_internal_dining_entries(self):
        user = User.objects.create_user('piet')
        list = DiningList.objects.create(date=date(2016, 2, 2))
        internal = DiningEntry.objects.create(dining_list=list, user=user)
        external = DiningEntry.objects.create(dining_list=list, user=user, external_name="Klaas")
        queryset = list.internal_dining_entries().all()
        self.assertEqual(1, len(queryset))
        self.assertEqual(internal.pk, queryset[0].pk)
