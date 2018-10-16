from django.test import TestCase
from .models import UserDiningStats, DiningList, DiningEntry, DiningEntryExternal
from CreditManagement.models import UserCredit
from UserDetails.models import User, Association
from django.utils import timezone
from decimal import Decimal

# Create your tests here.




class DiningTestCase(TestCase):
    def setUp(self):
        self.createTestEnvironment()

    def createTestEnvironment(self):
        User(pk=1, username="Person_A", password="test", email="test").save()
        User(pk=2, username="Person_B", password="test", email="test").save()

        Association(pk=1, name="Group_1").save()
        Association(pk=2, name="Group_2").save()


class UserDiningSettingTestClass(DiningTestCase):
    def test_basic_userdining_settings(self):
        userDineStats = User.objects.get(pk=1).userdiningstats
        userCredits = UserCredit.objects.get(pk=1).usercredit
        self.assertIsNotNone(userDineStats, "UserDiningStats was not autogenerated")
        self.assertTrue(float(userCredits.credit) == 0.0, "User credit did not start at 0")
        self.assertIs(userDineStats.count_subscribed, 0, "User count_subscribed did not start at 0")
        self.assertIs(userDineStats.count_cleaned, 0, "User count_cleaned did not start at 0")
        self.assertIs(userDineStats.count_cooked, 0, "User count_cooked did not start at 0")
        self.assertIs(userDineStats.count_shopped, 0, "User count_shopped did not start at 0")




class DiningListTest(DiningTestCase):
    def test_dining_list_normal(self):
        """
        Test the standard dining_list on a non-auto_pay model
        Tests credit flow on sign-up and off (kitchen_cost)
        Tests count increases
        """
        u1 = User.objects.get(pk=1)
        u2 = User.objects.get(pk=2)
        # Set the counts to an arbitrary number to ensure addition and substraction is used hwen adjusting count numbers
        count_value = 7.0
        u1.userdiningstats.count_cleaned = u1.userdiningstats.count_shopped = \
            u1.userdiningstats.count_subscribed = u1.userdiningstats.count_cooked = \
            u2.userdiningstats.count_cleaned = u2.userdiningstats.count_shopped = \
            u2.userdiningstats.count_subscribed = u2.userdiningstats.count_cooked = \
            u1.usercredit.credit = u2.usercredit.credit = \
            count_value
        u1.userdiningstats.save()
        u1.usercredit.save()
        u2.userdiningstats.save()
        u2.usercredit.save()

        # Set up the dining list and 5 entries
        dining_list = DiningList(kitchen_cost=Decimal('0.5'), date=timezone.now().date(),
                                 dinner_cost_total=Decimal('12'), claimed_by=u1)
        dining_list.save()
        self.assertEqual(float(UserCredit.objects.get(pk=1).credit), 0.0 + count_value, "Credits unjustly altered")

        DiningEntry(user=u1, dining_list=dining_list, has_cooked=True).save()
        DiningEntry(user=u2, dining_list=dining_list, has_cleaned=True).save()
        DiningEntryExternal(dining_list=dining_list, name="A", user=u2).save()
        DiningEntryExternal(dining_list=dining_list, name="B", user=u1).save()
        DiningEntryExternal(dining_list=dining_list, name="C", user=u2).save()

        # Check the state
        self.assertEqual(float(DiningList.objects.get(claimed_by=u1).dinner_cost_single), 2.40, "Incorrect price")
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), -1.0 + count_value, "Credits unjustly altered 1")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), -1.5 + count_value, "Credits unjustly altered 2")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_cooked), 1 + count_value, "Cook count incorrect 3")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=2).count_cleaned), 1 + count_value, "cleaned count incorrect 4")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=2).count_subscribed), 1 + count_value, "Subscribe not added 5")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_subscribed), 1 + count_value, "Subscribe not added 6")

        # Remove an entry and an external entry and check the status
        DiningEntry.objects.get(dining_list=dining_list, user=u2).delete()
        DiningEntryExternal.objects.get(name="B").delete()
        self.assertEqual(float(DiningList.objects.get(claimed_by=u1).dinner_cost_single), 4.0, "Incorrect price")
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), -0.5 + count_value, "Credits incorrectly altered 7")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), -1.0 + count_value, "Credits incorrectly altered 8")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=2).count_cleaned), 0 + count_value, "cleaned count not retracted 9")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=2).count_subscribed), 0 + count_value, "Subscribe not retracted 10")

        # Alter the cost of the kitchen
        dining_list = DiningList.objects.get(claimed_by=u1)
        dining_list.kitchen_cost = Decimal('0.8')
        dining_list.save()
        dining_list = DiningList.objects.get(claimed_by=u1)

        # Add an external and a normal entry again
        DiningEntryExternal(dining_list=dining_list, name="D", user=u1).save()
        DiningEntry(user=u2, dining_list=dining_list).save()

        # Check the state again
        self.assertEqual(float(DiningList.objects.get(claimed_by=u1).get_credit_cost()), 0.8, "Incorrect price 11")
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), -1.6 + count_value, "Credits incorrect 12")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), -2.40 + count_value, "Credits incorrect 13")

        # Change entry state
        d1 = DiningEntry.objects.get(dining_list=dining_list, user=u1)
        d1.has_cooked = False
        d1.has_shopped = True
        d1.save()

        # Check entry state of all 3 parameters
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_cooked), 0 + count_value, "Cook count incorrect 14")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_shopped), 1 + count_value, "Shopped count incorrect 15")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_cleaned), 0 + count_value, "Shopped count incorrect 16")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_subscribed), 1 + count_value, "Subscribe unjustly changed 17")

        # Delete the list and see if everything has reverted to it's original state
        dining_list.delete()
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), 0.0 + count_value, "Credits not properly reverted 18")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), 0.0 + count_value, "Credits not properly reverted 19")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_shopped), 0 + count_value, "Shopped count not retracted 20")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_cleaned), 0 + count_value, "Cleaned count not retracted 21")
        self.assertEqual(int(UserDiningStats.objects.get(user__pk=1).count_subscribed), 0 + count_value, "Subscribe not retracted properly 21")

    def test_dining_list_auto_pay(self):
        """
        Tes the credit flows on a dining_list with auto_pay
        """
        u1 = User.objects.get(pk=1)
        u2 = User.objects.get(pk=2)
        # Set the counts to an arbitrary number to ensure addition and substraction is used hwen adjusting count numbers
        count_value = 7.0
        u1.userdiningstats.count_cleaned = u1.userdiningstats.count_shopped = \
            u1.userdiningstats.count_subscribed = u1.userdiningstats.count_cooked = \
            u2.userdiningstats.count_cleaned = u2.userdiningstats.count_shopped = \
            u2.userdiningstats.count_subscribed = u2.userdiningstats.count_cooked = \
            u1.usercredit.credit = u2.usercredit.credit = \
            count_value
        u1.userdiningstats.save()
        u1.usercredit.save()
        u2.userdiningstats.save()
        u2.usercredit.save()

        dining_list = DiningList(kitchen_cost=Decimal('0.5'), date=timezone.now().date(),
                                 dinner_cost_total=Decimal('12'), claimed_by=u1, auto_pay=True)
        dining_list.save()
        self.assertEqual(float(UserCredit.objects.get(pk=1).credit), 0.0 + count_value, "Credits unjustly altered")

        # Add two users on an pay-active list
        de1 = DiningEntry(user=u1, dining_list=dining_list)
        de1.save()
        de2 = DiningEntry(user=u2, dining_list=dining_list)
        de2.save()
        self.assertEqual(float(DiningList.objects.get(claimed_by=u1).dinner_cost_single), 6.0, "Incorrect price")
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), 5.5 + count_value, "Credits incorrectly altered 1")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), -6.5 + count_value, "Credits incorrectly altered 2")

        # Change the costs of the dining list
        dining_list = DiningList.objects.get(pk=dining_list.pk)
        dining_list.dinner_cost_total = 10
        dining_list.save()
        self.assertEqual(float(DiningList.objects.get(claimed_by=u1).dinner_cost_single), 5.0, "Incorrect price")
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), 4.5 + count_value, "Credits incorrectly altered 3")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), -5.5 + count_value, "Credits incorrectly altered 4")
        # disable auto_pay
        dining_list.auto_pay = False
        dining_list.save()
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), -0.5 + count_value, "Credits incorrectly altered 5")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), -0.5 + count_value, "Credits incorrectly altered 6")

        # Enable auto_pay, remove someone from the dining list
        dining_list.auto_pay = True
        dining_list.save()
        de1.delete()
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), 10 + count_value, "Credits incorrectly altered 7")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), -10.5 + count_value, "Credits incorrectly altered 8")
        # clear the last entry on the list
        de2.delete()
        # ensure that the purchaser doesn't get the credits as the credits have no source
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), 0 + count_value, "Credits incorrectly altered 9")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), 0 + count_value, "Credits incorrectly altered 10")

        # Ccreate the list with an external entry
        de1 = DiningEntryExternal(user=u1, name="Johny Bravo", dining_list=dining_list)
        de1.save()
        self.assertEqual(float(DiningList.objects.get(claimed_by=u1).dinner_cost_single), 10.0, "Incorrect price")
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), -0.5 + count_value, "Credits unjustly altered 11")
        # Add a normal entry
        de2 = DiningEntry(user=u2, dining_list=dining_list)
        de2.save()
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), 4.5 + count_value, "Credits incorrectly altered 12")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), -5.5 + count_value, "Credits incorrectly altered 13")
        # Change the purchaser
        dining_list = DiningList.objects.get(pk=dining_list.pk)
        dining_list.purchaser = u2
        dining_list.save()
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), -5.5 + count_value, "Credits incorrectly altered 14")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), 4.5 + count_value, "Credits incorrectly altered 15")
        # Clear the entire list in a cascade effect
        dining_list.delete()
        self.assertEqual(float(UserCredit.objects.get(user__pk=1).credit), 0 + count_value, "Credits incorrectly altered 16")
        self.assertEqual(float(UserCredit.objects.get(user__pk=2).credit), 0 + count_value, "Credits incorrectly altered 17")




"""
manage.py test Dining.tests.DiningListTest.test_dining_list_auto_pay
      
"""