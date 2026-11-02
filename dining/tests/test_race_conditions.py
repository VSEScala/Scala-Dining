from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils.timezone import make_aware, now

from creditmanagement.models import Account, Transaction
from dining.forms import (
    CreateSlotForm,
    DiningEntryDeleteForm,
    DiningEntryExternalForm,
    DiningEntryInternalForm,
    DiningListDeleteForm,
)
from dining.models import DiningEntry, DiningList
from userdetails.models import Association, User, UserMembership


class DiningRaceConditionTestCase(TestCase):
    """Tests confirming race conditions in dining list workflows.

    1. Joining and leaving dining lists (double refunds, balance overdraw, duplicate entries)
    2. Creating and deleting dining lists (double refunds, slot collisions)
    3. Adding and removing people from dining lists (double refunds for external/other users)
    """

    def setUp(self):
        self.association = Association.objects.create(
            name="Test Association", slug="test-assoc"
        )
        self.owner = User.objects.create_user("owner", email="owner@example.com")
        self.diner = User.objects.create_user("diner", email="diner@example.com")
        self.other_user = User.objects.create_user("other", email="other@example.com")

        UserMembership.objects.create(
            related_user=self.owner,
            association=self.association,
            is_verified=True,
            verified_on=now(),
        )
        UserMembership.objects.create(
            related_user=self.diner,
            association=self.association,
            is_verified=True,
            verified_on=now(),
        )

        self.dining_date = now().date() + timedelta(days=2)
        self.dining_list = DiningList.objects.create(
            date=self.dining_date,
            association=self.association,
            sign_up_deadline=make_aware(
                datetime.combine(self.dining_date, time(15, 0))
            ),
            kitchen_cost=Decimal("0.50"),
        )
        self.dining_list.owners.add(self.owner)

    def test_leaving_double_refund_race_condition(self):
        """Simulates two concurrent leave requests on the same dining entry.

        When two requests load the entry concurrently before deletion,
        both must NOT process a refund.
        """
        entry = DiningEntry.objects.create(
            dining_list=self.dining_list,
            user=self.diner,
            created_by=self.diner,
            transaction=Transaction.objects.create(
                source=self.diner.account,
                target=Account.objects.get(special="kitchen_cost"),
                amount=Decimal("0.50"),
                description=f"Kitchen cost for {self.dining_list}",
                created_by=self.diner,
            ),
        )

        self.assertEqual(self.diner.account.get_balance(), Decimal("-0.50"))

        # In concurrent requests, both threads fetch their own entry instance
        entry1 = DiningEntry.objects.get(pk=entry.pk)
        entry2 = DiningEntry.objects.get(pk=entry.pk)

        form1 = DiningEntryDeleteForm(entry1, self.diner, {})
        form2 = DiningEntryDeleteForm(entry2, self.diner, {})
        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.execute()
        form2.execute()

        refund_transactions = Transaction.objects.filter(
            source=Account.objects.get(special="kitchen_cost"),
            target=self.diner.account,
        )
        self.assertEqual(
            refund_transactions.count(),
            1,
            "Multiple refunds were created for a single dining entry removal!",
        )
        self.assertEqual(
            self.diner.account.get_balance(),
            Decimal("0.00"),
            "User balance received duplicate refunds, stealing money from kitchen_cost!",
        )

    def test_removing_external_person_double_refund_race_condition(self):
        """Simulates two concurrent removal requests of an external guest."""
        entry = DiningEntry.objects.create(
            dining_list=self.dining_list,
            user=self.owner,
            created_by=self.owner,
            external_name="External Guest",
            transaction=Transaction.objects.create(
                source=self.owner.account,
                target=Account.objects.get(special="kitchen_cost"),
                amount=Decimal("0.50"),
                description=f"Kitchen cost for {self.dining_list}",
                created_by=self.owner,
            ),
        )

        self.assertEqual(self.owner.account.get_balance(), Decimal("-0.50"))

        entry1 = DiningEntry.objects.get(pk=entry.pk)
        entry2 = DiningEntry.objects.get(pk=entry.pk)

        form1 = DiningEntryDeleteForm(entry1, self.owner, {})
        form2 = DiningEntryDeleteForm(entry2, self.owner, {})
        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.execute()
        form2.execute()

        refund_transactions = Transaction.objects.filter(
            source=Account.objects.get(special="kitchen_cost"),
            target=self.owner.account,
        )
        self.assertEqual(
            refund_transactions.count(),
            1,
            "Multiple refunds were created for external guest removal!",
        )
        self.assertEqual(self.owner.account.get_balance(), Decimal("0.00"))

    def test_list_deletion_double_refund_race_condition(self):
        """Simulates two concurrent delete requests on the same dining list.

        When a dining list is deleted, the owner must NOT be refunded twice.
        """
        DiningEntry.objects.create(
            dining_list=self.dining_list,
            user=self.owner,
            created_by=self.owner,
            transaction=Transaction.objects.create(
                source=self.owner.account,
                target=Account.objects.get(special="kitchen_cost"),
                amount=Decimal("0.50"),
                description=f"Kitchen cost for {self.dining_list}",
                created_by=self.owner,
            ),
        )

        dl1 = DiningList.objects.prefetch_related("dining_entries").get(
            pk=self.dining_list.pk
        )
        dl2 = DiningList.objects.prefetch_related("dining_entries").get(
            pk=self.dining_list.pk
        )

        form1 = DiningListDeleteForm({"reason": "Cancel 1"}, instance=dl1)
        form2 = DiningListDeleteForm({"reason": "Cancel 2"}, instance=dl2)
        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.execute(self.owner)
        form2.execute(self.owner)

        owner_refunds = Transaction.objects.filter(
            source=Account.objects.get(special="kitchen_cost"),
            target=self.owner.account,
        )
        self.assertEqual(
            owner_refunds.count(),
            1,
            "Owner received duplicate refunds from concurrent list deletions!",
        )
        self.assertEqual(self.owner.account.get_balance(), Decimal("0.00"))

    def test_concurrent_list_deletion_with_diners_does_not_crash(self):
        """Simulates concurrent list deletion when other diners exist.

        A second concurrent deletion request must not crash with an unhandled RuntimeError
        due to orphaned permissions.
        """
        DiningEntry.objects.create(
            dining_list=self.dining_list,
            user=self.diner,
            created_by=self.diner,
            transaction=Transaction.objects.create(
                source=self.diner.account,
                target=Account.objects.get(special="kitchen_cost"),
                amount=Decimal("0.50"),
                description=f"Kitchen cost for {self.dining_list}",
                created_by=self.diner,
            ),
        )

        dl1 = DiningList.objects.prefetch_related("dining_entries").get(
            pk=self.dining_list.pk
        )
        dl2 = DiningList.objects.prefetch_related("dining_entries").get(
            pk=self.dining_list.pk
        )

        form1 = DiningListDeleteForm({"reason": "Cancel 1"}, instance=dl1)
        form2 = DiningListDeleteForm({"reason": "Cancel 2"}, instance=dl2)
        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.execute(self.owner)
        # In a race-safe system, this must not raise RuntimeError
        try:
            form2.execute(self.owner)
        except RuntimeError as e:
            self.fail(
                f"Concurrent list deletion crashed with unhandled RuntimeError: {e}"
            )

    def test_concurrent_leave_and_list_deletion_double_refund(self):
        """Simulates a diner leaving at the exact moment the owner deletes the list."""
        entry = DiningEntry.objects.create(
            dining_list=self.dining_list,
            user=self.diner,
            created_by=self.diner,
            transaction=Transaction.objects.create(
                source=self.diner.account,
                target=Account.objects.get(special="kitchen_cost"),
                amount=Decimal("0.50"),
                description=f"Kitchen cost for {self.dining_list}",
                created_by=self.diner,
            ),
        )

        entry1 = DiningEntry.objects.get(pk=entry.pk)
        dl1 = DiningList.objects.prefetch_related("dining_entries").get(
            pk=self.dining_list.pk
        )

        entry_form = DiningEntryDeleteForm(entry1, self.diner, {})
        list_form = DiningListDeleteForm({"reason": "Cancelled"}, instance=dl1)
        self.assertTrue(entry_form.is_valid())
        self.assertTrue(list_form.is_valid())

        # Diner leaves
        entry_form.execute()
        # Owner deletes list
        list_form.execute(self.owner)

        diner_refunds = Transaction.objects.filter(
            source=Account.objects.get(special="kitchen_cost"),
            target=self.diner.account,
        )
        self.assertEqual(
            diner_refunds.count(),
            1,
            "Diner received duplicate refunds from concurrent leave + list deletion!",
        )
        self.assertEqual(self.diner.account.get_balance(), Decimal("0.00"))

    def test_concurrent_joins_overdraw_account_balance(self):
        """Simulates concurrent join requests when user balance is near the minimum limit.

        MINIMUM_BALANCE_FOR_DINING_SIGN_UP = -2.00 + KITCHEN_COST = -1.50.
        If a user has -1.50 balance, they can afford only ONE entry (bringing balance to -2.00).
        If two join requests validate concurrently, the second save must fail rather than
        overdrawing the account below the allowed minimum (-2.00).
        """
        # Set diner balance to -1.50
        Transaction.objects.create(
            source=self.diner.account,
            target=Account.objects.get(special="kitchen_cost"),
            amount=Decimal("1.50"),
            description="Initial debt",
            created_by=self.diner,
        )
        self.assertEqual(self.diner.account.get_balance(), Decimal("-1.50"))

        # Create a second dining list for another association
        assoc2 = Association.objects.create(name="Assoc 2", slug="assoc-2")
        dl2 = DiningList.objects.create(
            date=self.dining_date,
            association=assoc2,
            sign_up_deadline=make_aware(
                datetime.combine(self.dining_date, time(15, 0))
            ),
            kitchen_cost=Decimal("0.50"),
        )
        dl2.owners.add(self.owner)

        entry1 = DiningEntry(dining_list=self.dining_list, created_by=self.diner)
        entry2 = DiningEntry(dining_list=dl2, created_by=self.diner)

        form1 = DiningEntryInternalForm({"user": str(self.diner.pk)}, instance=entry1)
        form2 = DiningEntryInternalForm({"user": str(self.diner.pk)}, instance=entry2)

        # Both forms validate concurrently when balance is -1.50
        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.save()
        # Balance is now -2.00 (at the absolute limit)
        self.assertEqual(self.diner.account.get_balance(), Decimal("-2.00"))

        # Saving form2 should be rejected because the balance is now insufficient
        with self.assertRaises((ValidationError, IntegrityError)):
            form2.save()
        self.assertEqual(self.diner.account.get_balance(), Decimal("-2.00"))

    def test_concurrent_internal_entries_same_user_same_list(self):
        """Simulates two concurrent join requests by the same user to the same dining list.

        A user must not be added to the same dining list more than once.
        """
        entry1 = DiningEntry(dining_list=self.dining_list, created_by=self.diner)
        entry2 = DiningEntry(dining_list=self.dining_list, created_by=self.diner)

        form1 = DiningEntryInternalForm({"user": str(self.diner.pk)}, instance=entry1)
        form2 = DiningEntryInternalForm({"user": str(self.diner.pk)}, instance=entry2)

        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.save()

        # Second save must fail (via ValidationError or DB IntegrityError)
        with self.assertRaises((ValidationError, IntegrityError)):
            form2.save()

    def test_concurrent_create_slot_same_date_and_association(self):
        """Simulates two concurrent slot creation requests for the same association on the same date."""
        data = {
            "dish": "Pasta",
            "association": str(self.association.pk),
            "max_diners": "18",
            "serve_time": "17:00",
        }
        # Delete existing list on this date so slot is open
        self.dining_list.delete()

        dl1 = DiningList(date=self.dining_date)
        dl2 = DiningList(date=self.dining_date)

        form1 = CreateSlotForm(self.owner, data, instance=dl1)
        form2 = CreateSlotForm(self.owner, data, instance=dl2)

        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.save()

        # Second save must fail because the association already has a list on this date
        with self.assertRaises((ValidationError, IntegrityError)):
            form2.save()

    def test_concurrent_additions_exceed_max_diners(self):
        """Simulates concurrent additions when only 1 spot remains on the dining list.

        Two diners submit join requests concurrently. The list capacity must not be exceeded.
        """
        self.dining_list.max_diners = 1
        self.dining_list.save()

        user_a = User.objects.create_user("user_a", email="user_a@example.com")
        user_b = User.objects.create_user("user_b", email="user_b@example.com")

        entry_a = DiningEntry(dining_list=self.dining_list, created_by=user_a)
        entry_b = DiningEntry(dining_list=self.dining_list, created_by=user_b)

        form_a = DiningEntryInternalForm({"user": str(user_a.pk)}, instance=entry_a)
        form_b = DiningEntryInternalForm({"user": str(user_b.pk)}, instance=entry_b)

        self.assertTrue(form_a.is_valid())
        self.assertTrue(form_b.is_valid())

        form_a.save()
        # List is now at max_diners (1/1)
        self.assertEqual(self.dining_list.dining_entries.count(), 1)

        # Second addition should be rejected
        with self.assertRaises((ValidationError, IntegrityError)):
            form_b.save()

    def test_concurrent_create_slots_exceed_max_slot_number(self):
        """Simulates concurrent slot creation when only 1 available slot remains on the day.

        The total number of dining slots on a date must not exceed MAX_SLOT_NUMBER.
        """
        self.dining_list.delete()

        # Create MAX_SLOT_NUMBER - 1 slots for other associations
        for i in range(settings.MAX_SLOT_NUMBER - 1):
            assoc = Association.objects.create(name=f"Assoc {i}", slug=f"assoc-{i}")
            DiningList.objects.create(
                date=self.dining_date,
                association=assoc,
                sign_up_deadline=make_aware(
                    datetime.combine(self.dining_date, time(15, 0))
                ),
            )

        self.assertEqual(DiningList.objects.available_slots(self.dining_date), 1)

        assoc_a = Association.objects.create(name="Assoc A", slug="assoc-a")
        assoc_b = Association.objects.create(name="Assoc B", slug="assoc-b")
        user_a = User.objects.create_user(
            "user_slot_a", email="user_slot_a@example.com"
        )
        user_b = User.objects.create_user(
            "user_slot_b", email="user_slot_b@example.com"
        )
        UserMembership.objects.create(
            related_user=user_a,
            association=assoc_a,
            is_verified=True,
            verified_on=now(),
        )
        UserMembership.objects.create(
            related_user=user_b,
            association=assoc_b,
            is_verified=True,
            verified_on=now(),
        )

        dl_a = DiningList(date=self.dining_date)
        dl_b = DiningList(date=self.dining_date)

        form_a = CreateSlotForm(
            user_a,
            {
                "dish": "Dish A",
                "association": str(assoc_a.pk),
                "max_diners": "18",
                "serve_time": "17:00",
            },
            instance=dl_a,
        )
        form_b = CreateSlotForm(
            user_b,
            {
                "dish": "Dish B",
                "association": str(assoc_b.pk),
                "max_diners": "18",
                "serve_time": "17:00",
            },
            instance=dl_b,
        )

        self.assertTrue(form_a.is_valid())
        self.assertTrue(form_b.is_valid())

        form_a.save()
        self.assertEqual(
            DiningList.objects.filter(date=self.dining_date).count(),
            settings.MAX_SLOT_NUMBER,
        )

        # Second save must fail because max slots for the day is reached
        with self.assertRaises((ValidationError, IntegrityError)):
            form_b.save()

    def test_concurrent_create_slots_same_owner_same_date(self):
        """Simulates a user attempting to claim two dining lists on the same date concurrently."""
        self.dining_list.delete()

        assoc2 = Association.objects.create(name="Assoc 2", slug="assoc-2")
        UserMembership.objects.create(
            related_user=self.owner,
            association=assoc2,
            is_verified=True,
            verified_on=now(),
        )

        dl1 = DiningList(date=self.dining_date)
        dl2 = DiningList(date=self.dining_date)

        form1 = CreateSlotForm(
            self.owner,
            {
                "dish": "Dish 1",
                "association": str(self.association.pk),
                "max_diners": "18",
                "serve_time": "17:00",
            },
            instance=dl1,
        )
        form2 = CreateSlotForm(
            self.owner,
            {
                "dish": "Dish 2",
                "association": str(assoc2.pk),
                "max_diners": "18",
                "serve_time": "17:00",
            },
            instance=dl2,
        )

        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.save()

        # Second save must fail because the owner already owns a list on this date
        with self.assertRaises((ValidationError, IntegrityError)):
            form2.save()

    def test_concurrent_external_additions_overdraw_account(self):
        """Simulates concurrent additions of external diners overdrawing the adder's account."""
        Transaction.objects.create(
            source=self.owner.account,
            target=Account.objects.get(special="kitchen_cost"),
            amount=Decimal("1.50"),
            description="Initial debt",
            created_by=self.owner,
        )
        self.assertEqual(self.owner.account.get_balance(), Decimal("-1.50"))

        entry1 = DiningEntry(
            dining_list=self.dining_list, created_by=self.owner, user=self.owner
        )
        entry2 = DiningEntry(
            dining_list=self.dining_list, created_by=self.owner, user=self.owner
        )

        form1 = DiningEntryExternalForm({"external_name": "Guest 1"}, instance=entry1)
        form2 = DiningEntryExternalForm({"external_name": "Guest 2"}, instance=entry2)

        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.save()
        self.assertEqual(self.owner.account.get_balance(), Decimal("-2.00"))

        # Second save must fail because adder cannot afford it
        with self.assertRaises((ValidationError, IntegrityError)):
            form2.save()
        self.assertEqual(self.owner.account.get_balance(), Decimal("-2.00"))

    def test_concurrent_additions_same_target_user_by_different_adders(self):
        """Simulates two different users attempting to add the same target user concurrently."""
        entry1 = DiningEntry(dining_list=self.dining_list, created_by=self.owner)
        entry2 = DiningEntry(dining_list=self.dining_list, created_by=self.diner)

        form1 = DiningEntryInternalForm(
            {"user": str(self.other_user.pk)}, instance=entry1
        )
        form2 = DiningEntryInternalForm(
            {"user": str(self.other_user.pk)}, instance=entry2
        )

        self.assertTrue(form1.is_valid())
        self.assertTrue(form2.is_valid())

        form1.save()

        # Second save must fail because target user is already added
        with self.assertRaises((ValidationError, IntegrityError)):
            form2.save()
