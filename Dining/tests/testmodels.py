from datetime import date

from django.test import TestCase

from Dining.models import DiningEntryUser, DiningList, DiningEntry, DiningEntryExternal
from UserDetails.models import Association, User


class DiningEntryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('piet')
        cls.association = Association.objects.create(slug='assoc')
        cls.dining_list = DiningList.objects.create(date=date(2123, 2, 1), association=cls.association,
                                                    claimed_by=cls.user)

    def test_get_internal_true(self):
        entry = DiningEntryUser(dining_list=self.dining_list, user=self.user)
        entry.save()
        self.assertEqual(entry, entry.get_internal())  # Direct call
        self.assertEqual(entry, DiningEntry.objects.get(pk=entry.pk).get_internal())  # Indirect call
        self.assertEqual(entry, DiningEntryUser.objects.get(pk=entry.pk).get_internal())  # Indirect call 2

    def test_get_internal_false(self):
        entry = DiningEntryExternal.objects.create(dining_list=self.dining_list, user=self.user, name='Jan')
        self.assertIsNone(entry.get_internal())  # Direct call
        self.assertIsNone(DiningEntry.objects.get(pk=entry.pk).get_internal())  # Indirect call
