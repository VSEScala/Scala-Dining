from django.test import TestCase
from CreditManagement.models import Transaction, AssociationCredit, UserCredit
from UserDetails.models import UserInformation, Association
from django.utils import timezone
from decimal import Decimal


# Create your tests here.
class CreditTestBase(TestCase):
    def setUp(self):
        self.createTestEnvironment()

    def createTestEnvironment(self):
        UserInformation(pk=1, username="Person_A", password="test", email="test").save()
        UserInformation(pk=2, username="Person_B", password="test", email="test").save()

        Association(pk=1, name="Group_1").save()
        Association(pk=2, name="Group_2").save()


class AssociationCreditsTestClass(CreditTestBase):
    def test_association_credits(self):
        associationcredit = Association.objects.get(pk=1).get_credit_containing_instance()
        self.assertIsNotNone(associationcredit, "No active association credits returned")

        associationcredit.credit = 3.0
        associationcredit.save()
        self.assertTrue(float(AssociationCredit.objects.get(pk=associationcredit.pk).credit) == 3.0, "Credits were not adjusted")
        associationcredit.end_date = timezone.now()
        associationcredit.credit = 0.0
        associationcredit.save()
        new_assoc_credit = Association.objects.get(pk=1).get_credit_containing_instance()
        self.assertTrue(float(AssociationCredit.objects.get(pk=associationcredit.pk).credit) == 0.0, "Credits were not adjusted")
        self.assertIsNotNone(new_assoc_credit, "No active associationcredits are present after ending the previous")
        associationcredit.credit = 5.0
        associationcredit.save()
        self.assertTrue(float(AssociationCredit.objects.get(pk=associationcredit.pk).credit) == 0.0, "Closed associationCredit was able to change credit")
        associationcredit.credit = None
        associationcredit.save()
        self.assertIsNotNone(AssociationCredit.objects.get(pk=associationcredit.pk).end_date, "End date on ended asoociationCredit was able to be removed")


class TransactionTest(CreditTestBase):

    def test_transaction_flow(self):
        u1 = UserInformation.objects.get(pk=1)
        u2 = UserInformation.objects.get(pk=2)
        transaction = Transaction(target_user=u2, source_user=u1, amount=5)
        transaction.save()

        self.assertEqual(float(UserCredit.objects.get(pk=u1.pk).credit), -5.0, "Money was not taken from source account U->U")
        self.assertEqual(float(UserCredit.objects.get(pk=u2.pk).credit), 5.0, "Money was not given to target account U->U")

        # Change Source
        a1 = Association.objects.get(pk=1)
        transaction.source_association = a1
        transaction.save()
        self.assertEqual(float(UserCredit.objects.get(pk=u1.pk).credit), 0.0, "Money was not returned to old source user account")
        self.assertEqual(float(AssociationCredit.objects.get(association=a1).credit), -5.0, "Money was not taken from new source account A->U")

        # Change amount and target
        a2 = Association.objects.get(pk=2)
        transaction.target_association = a2
        transaction.target_user = None
        transaction.amount = Decimal('2.50')
        transaction.save()
        self.assertEqual(float(UserCredit.objects.get(pk=u2.pk).credit), 0.0, "Money was not subtracted properly from target user")
        self.assertEqual(float(AssociationCredit.objects.get(association=a2).credit), 2.5, "Money was given to the new target A->A")
        self.assertEqual(float(AssociationCredit.objects.get(association=a1).credit), -2.5, "Money was not adjusted on the new source A->A")

        # Change source back to user
        transaction.source_user = u2
        transaction.source_association = None
        transaction.save()
        self.assertEqual(float(UserCredit.objects.get(pk=u2.pk).credit), -2.5, "Money was not taken from the new source")
        self.assertEqual(float(AssociationCredit.objects.get(association=a1).credit), 0.0, "Money was not returned to the old source U->A")

        # Test faulty transaction
        """
        u3 = UserInformation(pk=3, username="Person_C", password="test", email="test")
        transaction.target_user = u3
        transaction.target_association = None
        transaction.save()
        """

        transaction.delete()
        self.assertEqual(float(UserCredit.objects.get(pk=u2.pk).credit), 0.0, "Money was not returned to source upon deletion")
        self.assertEqual(float(a2.get_credit_containing_instance().credit), 0.0, "Money was not retracted upon delete")


"""
manage.py test CreditManagement.tests.TransactionTest
"""