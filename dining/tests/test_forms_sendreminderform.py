import threading
from datetime import date, datetime

from django.db import OperationalError, connections, transaction
from django.http import HttpRequest
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone

from dining.forms import SendReminderForm
from dining.models import DiningEntry, DiningList
from userdetails.models import Association, User


class SendReminderFormTestCase(TestCase):
    """Tests SendReminderForm.

    It is not necessary to test the clean() method. The validation is only for
    UX to give a nice message. The method doesn't have any interesting behavior.
    """

    @classmethod
    def setUpTestData(cls):
        cls.dining_list = DiningList.objects.create(
            date=date(2020, 1, 1),
            association=Association.objects.create(slug="assoc"),
            sign_up_deadline=datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc),
        )
        cls.user = User.objects.create()

    def setUp(self):
        self.form = SendReminderForm({}, dining_list=self.dining_list)

    def create_dining_entry(self, user: User, has_paid: bool, guest_name=None):
        """Helper to quickly create a dining entry."""
        if guest_name:
            DiningEntry.objects.create(
                user=user,
                dining_list=self.dining_list,
                created_by=user,
                has_paid=has_paid,
                external_name=guest_name,
            )
        else:
            DiningEntry.objects.create(
                user=user,
                dining_list=self.dining_list,
                created_by=user,
                has_paid=has_paid,
            )

    def test_user_paid(self):
        """Tests that a paid user is not included."""
        self.create_dining_entry(self.user, has_paid=True)
        self.assertEqual(list(self.form.get_user_recipients()), [])
        self.assertEqual(self.form.get_guest_recipients(), {})

    def test_user_not_paid(self):
        """Tests that a non paid user is included."""
        self.create_dining_entry(self.user, has_paid=False)
        self.assertEqual(list(self.form.get_user_recipients()), [self.user])
        self.assertEqual(self.form.get_guest_recipients(), {})

    def test_guest_paid(self):
        """Tests that a guest who paid is not included."""
        self.create_dining_entry(self.user, has_paid=True, guest_name="Guest")
        self.assertEqual(list(self.form.get_user_recipients()), [])
        self.assertEqual(self.form.get_guest_recipients(), {})

    def test_guest_not_paid(self):
        """Tests that a guest who didn't pay is included."""
        self.create_dining_entry(self.user, has_paid=False, guest_name="Guest")
        self.assertEqual(list(self.form.get_user_recipients()), [])
        self.assertEqual(self.form.get_guest_recipients(), {self.user: ["Guest"]})

    def test_two_guests(self):
        """Tests for two guests from one user."""
        self.create_dining_entry(self.user, has_paid=False, guest_name="Guest 1")
        self.create_dining_entry(self.user, has_paid=False, guest_name="Guest 2")
        self.assertEqual(list(self.form.get_user_recipients()), [])
        self.assertEqual(
            self.form.get_guest_recipients(), {self.user: ["Guest 1", "Guest 2"]}
        )

    def test_arbitrary(self):
        """Tests with an arbitrary dining list with all cases.

        Not really necessary. But to make sure that we didn't miss a corner
        case above. We also verify construct_messages().
        """
        # Create 4 users.
        u = [
            User.objects.create(username=f"{i}", email=f"{i}@localhost")
            for i in range(4)
        ]
        # Create 1 of each possible case.
        self.create_dining_entry(u[0], has_paid=False)
        self.create_dining_entry(u[1], has_paid=True)
        self.create_dining_entry(u[2], has_paid=False, guest_name="Guest 1")
        self.create_dining_entry(
            u[2], has_paid=False, guest_name="Guest 2"
        )  # Same user, different guest
        self.create_dining_entry(u[3], has_paid=True, guest_name="Guest 3")

        self.assertEqual(list(self.form.get_user_recipients()), [u[0]])
        self.assertEqual(
            self.form.get_guest_recipients(), {u[2]: ["Guest 1", "Guest 2"]}
        )

        # For construct_messages() we just confirm that it has the correct
        # recipients. If we wanted to test that the contexts are correct, we
        # would need to create a get_context() method or something similar. But
        # the code is so trivial that we don't need to test this.
        request = HttpRequest()
        request.user = u[0]
        messages = self.form.construct_messages(request)
        self.assertEqual([m.to for m in messages], [["0@localhost"], ["2@localhost"]])


class SendReminderFormLockTestCase(TransactionTestCase):
    """Tests that no simultaneous emails are sent.

    This needs to inherit from TransactionTestCase because we are testing
    code with a database transaction.
    """

    @skipUnlessDBFeature("has_select_for_update", "has_select_for_update_nowait")
    def test_send_reminder(self):
        """Tests that send_reminder() doesn't send multiple emails simultaneously."""
        form = SendReminderForm(
            {},
            dining_list=DiningList.objects.create(
                date=date(2020, 1, 1),
                association=Association.objects.create(slug="assoc"),
                sign_up_deadline=datetime(2020, 1, 1, 12, 0, tzinfo=timezone.utc),
            ),
        )
        request = HttpRequest()
        request.user = User.objects.create()

        # XD I generated this test case using ChatGPT. I used the prompt "How to unit test
        # a critical section in Python using Django select_for_update()?"

        with transaction.atomic():
            # Lock by sending the form. This should succeed. (There are 0
            # diners on the list but that's fine.)
            self.assertTrue(form.send_reminder(request))

            # While keeping the lock, try sending again from a different
            # thread. This will use a different database transaction and should
            # fail.
            self.exc = None

            def send_again():
                self.exc = None
                try:
                    form.send_reminder(request, nowait=True)
                except BaseException as e:
                    self.exc = e
                # This might be necessary according to https://stackoverflow.com/a/1346401/2373688.
                connections["default"].close()

            t = threading.Thread(target=send_again)
            t.start()
            t.join(timeout=5)
            # Verify that a database exception was raised, because the table is locked.
            self.assertIsInstance(self.exc, OperationalError)

        # After unlocking, sending should still fail momentarily
        self.assertFalse(form.send_reminder(request))
