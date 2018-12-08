from django.test import TestCase

from UserDetails.models import User, Association


class DiningTestCase(TestCase):
    def setUp(self):
        self.createTestEnvironment()

    def createTestEnvironment(self):
        User(pk=1, username="Person_A", password="test", email="test").save()
        User(pk=2, username="Person_B", password="test", email="test").save()

        Association(pk=1, name="Group_1").save()
        Association(pk=2, name="Group_2").save()


class DiningListTest(DiningTestCase):
    def test_dining_list_normal(self):
        # Deleted test case since credits need to be changed to transactions
        pass

    def test_dining_list_auto_pay(self):
        # See above
        pass
