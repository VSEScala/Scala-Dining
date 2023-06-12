from datetime import date, datetime
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from dining.models import DiningEntry, DiningList
from userdetails.models import Association, User


class DiningListTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("ankie")
        cls.association = Association.objects.create()

    def setUp(self):
        self.dining_list = DiningList(
            date=date(2123, 1, 2),
            sign_up_deadline=datetime(2100, 2, 2, tzinfo=timezone.utc),
            association=self.association,
        )

    def test_is_open(self):
        list = DiningList.objects.create(
            date=date(2015, 1, 1),
            association=self.association,
            sign_up_deadline=datetime(2015, 1, 1, 17, 00, tzinfo=timezone.utc),
        )

        with patch.object(
            timezone,
            "now",
            return_value=datetime(2015, 1, 1, 16, 59, tzinfo=timezone.utc),
        ):
            self.assertTrue(list.is_open())
        with patch.object(
            timezone,
            "now",
            return_value=datetime(2015, 1, 1, 17, 00, tzinfo=timezone.utc),
        ):
            self.assertFalse(list.is_open())
        with patch.object(
            timezone,
            "now",
            return_value=datetime(2015, 1, 1, 17, 1, tzinfo=timezone.utc),
        ):
            self.assertFalse(list.is_open())

    def test_is_owner(self):
        self.dining_list.save()
        self.dining_list.owners.add(self.user)
        self.assertTrue(self.dining_list.is_owner(self.user))

    def test_is_owner_false(self):
        self.dining_list.save()
        self.assertFalse(self.dining_list.is_owner(self.user))

    # Disabled as board members do not directly own all dining lists
    # def test_is_owner_board_member(self):
    #     # Make user board member
    #     self.association.user_set.add(self.user)
    #     self.dining_list.save()
    #     self.assertTrue(self.dining_list.is_owner(self.user))


class DiningListCleanTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("ankie")
        cls.association = Association.objects.create()

    def setUp(self):
        self.dining_list = DiningList(
            date=date(2123, 1, 2),
            sign_up_deadline=datetime(2100, 2, 2, tzinfo=timezone.utc),
            association=self.association,
        )

    def test_sign_up_deadline_valid(self):
        self.dining_list.full_clean()  # Shouldn't raise

    def test_sign_up_deadline_after_date(self):
        self.dining_list.sign_up_deadline = datetime(2123, 1, 3, 18, 00)
        self.assertRaises(ValidationError, self.dining_list.full_clean)


class DiningEntryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("piet")
        cls.dining_list = DiningList.objects.create(
            date=date(2123, 2, 1),
            association=Association.objects.create(slug="assoc"),
            sign_up_deadline=datetime(2100, 1, 1, tzinfo=timezone.utc),
        )

    def test_clean_valid_entry(self):
        entry = DiningEntry(
            dining_list=self.dining_list, user=self.user, created_by=self.user
        )
        entry.full_clean()  # No ValidationError

    def test_clean_duplicate_entry(self):
        DiningEntry.objects.create(
            dining_list=self.dining_list, user=self.user, created_by=self.user
        )
        entry = DiningEntry(
            dining_list=self.dining_list, user=self.user, created_by=self.user
        )
        self.assertRaises(ValidationError, entry.full_clean)

    def test_external_name(self):
        entry = DiningEntry(
            user=self.user,
            dining_list=self.dining_list,
            external_name="Piet",
            created_by=self.user,
        )
        entry.full_clean()  # No ValidationError
