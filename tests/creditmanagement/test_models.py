# from django.db import IntegrityError
# from django.test import TestCase
#
# from CreditManagement.models import Transaction
# from UserDetails.models import User, Association
#

# Todo: these tests are outdated
# class TransactionsDbConstraintsTestCase(TestCase):
#     """
#     Test cases for the transaction database constraints and that it is not possible to update or delete.
#     """
#
#     @classmethod
#     def setUpTestData(cls):
#         cls.user1 = User.objects.create_user('ankie')
#         cls.user2 = User.objects.create_user('noortje')
#         cls.association1 = Association.objects.create()
#
#     def test_transaction_constraints(self):
#         """
#         Tests the transaction constraints on the save() function.
#         """
#         # amount > 0
#         t = Transaction(amount=0, source_user=self.user1)
#         self.assertRaises(AssertionError, t.save)
#         t = Transaction(amount=-1, target_user=self.user2)
#         self.assertRaises(AssertionError, t.save)
#         # At most one source
#         t = Transaction(amount=1, source_user=self.user1, source_association=self.association1, target_user=self.user2)
#         self.assertRaises(AssertionError, t.save)
#         # At most one target
#         t = Transaction(amount=1, target_association=self.association1, target_user=self.user2)
#         self.assertRaises(AssertionError, t.save)
#         # At least a source or target
#         t = Transaction(amount=1)
#         self.assertRaises(AssertionError, t.save)
#
#     def test_transaction_constraints_on_db(self):
#         """
#         Tests the transaction constraints directly on the database.
#         """
#         # amount > 0
#         t = Transaction(amount=0, source_user=self.user1)
#         self.assertRaises(IntegrityError, super(Transaction, t).save)
#         t = Transaction(amount=-1, target_user=self.user2)
#         self.assertRaises(IntegrityError, super(Transaction, t).save)
#         # At most one source
#         t = Transaction(amount=1, source_user=self.user1, source_association=self.association1,
#                         target_user=self.user2)
#         self.assertRaises(IntegrityError, super(Transaction, t).save)
#         # At most one target
#         t = Transaction(amount=1, target_association=self.association1, target_user=self.user2)
#         self.assertRaises(IntegrityError, super(Transaction, t).save)
#         # At least a source or target
#         t = Transaction(amount=1)
#         self.assertRaises(IntegrityError, super(Transaction, t).save)
#
#     def test_update(self):
#         """
#         Tests if update is not possible.
#         """
#         t = Transaction(amount=1, source_user=self.user1)
#         t.save()
#         t.amount = 2
#         self.assertRaises(AssertionError, t.save)
#
#     def test_update_on_db(self):
#         """
#         Tests whether update is not possible when ran directly on the database.
#         """
#         t = Transaction(amount=1, source_user=self.user1)
#         t.save()
#         t.amount = 2
#         self.assertRaises(IntegrityError, super(Transaction, t).save)
#
#     def test_delete(self):
#         """
#         Tests if delete is not possible.
#         """
#         t = Transaction(amount=1, target_association=self.association1)
#         t.save()
#         self.assertRaises(AssertionError, t.delete)
#
#     def test_delete_on_db(self):
#         """
#         Tests whether delete is not possible when ran directly on the database.
#         """
#         t = Transaction(amount=1, target_association=self.association1)
#         t.save()
#         self.assertRaises(IntegrityError, super(Transaction, t).save)
