from django.test import TestCase
from django.utils import timezone

from datetime import time, timedelta

from UserDetails.models import Association, User, UserMembership
from CreditManagement.models import FixedTransaction
from Dining.forms import CreateSlotForm, DiningEntryUserCreateForm, DiningEntryExternalCreateForm, DiningCommentForm
from Dining.models import DiningList, DiningEntryUser, DiningEntryExternal, DiningComment

# Todo:
# Can add when association has exception check
# Can not alter allergies


class CreateSlotFormSuspendedTestCase(TestCase):
    def setUp(self):
        self.association = Association.objects.create(name='Knights')
        self.suspended_user = User.objects.create_user('Bobby boef', is_suspended=True, email="suspended@test.ing")
        self.active_user = User.objects.create_user('Eric de Engel', is_suspended=False, email="active@test.ing")

        self.dining_date = timezone.now().date() + timedelta(days=2)

        UserMembership.objects.create(related_user=self.suspended_user, association=self.association, is_verified=True,
                                      verified_on=timezone.now())
        UserMembership.objects.create(related_user=self.active_user, association=self.association, is_verified=True,
                                      verified_on=timezone.now())

    def test_cant_create_new_slot(self):
        form_data = {'dish': 'Can of Whoopass', 'association': str(self.association.pk), 'max_diners': '20',
                     'serve_time': '18:00'}

        # Check that suspended users can't create a dininglist
        self.form = CreateSlotForm(form_data, instance=DiningList(claimed_by=self.suspended_user, date=self.dining_date))
        self.assertFalse(self.form.is_valid())

        # Check that a non-suspended user can create a dining list
        self.form = CreateSlotForm(form_data, instance=DiningList(claimed_by=self.active_user, date=self.dining_date))
        self.assertTrue(self.form.is_valid())


class AddSuspendedOnDiningCase(TestCase):
    def setUp(self):
        self.association = Association.objects.create(name='Knights')
        self.suspended_user = User.objects.create_user('Bobby boef', is_suspended=True, email="suspended@test.ing")
        self.active_user = User.objects.create_user('Eric de Engel', is_suspended=False, email="active@test.ing")
        self.third_user =  User.objects.create_user('Pete Pion', is_suspended=False, email="pion@test.ing")

        UserMembership.objects.create(related_user=self.suspended_user, association=self.association, is_verified=True,
                                      verified_on=timezone.now())
        UserMembership.objects.create(related_user=self.active_user, association=self.association, is_verified=True,
                                      verified_on=timezone.now())

        dining_date = timezone.now().date() + timedelta(days=2)
        deadline = timezone.now() + timedelta(days=1)
        self.dining_list = DiningList.objects.create(claimed_by=self.active_user,
                                                     association=self.association,
                                                     date=dining_date, sign_up_deadline=deadline)

    def test_add_user(self):
        form_data = {'user': self.suspended_user.pk}

        # Check that the suspended user can not add himself because his balance would be below 0
        entry = DiningEntryUser(dining_list=self.dining_list, created_by=self.suspended_user)
        form = DiningEntryUserCreateForm(form_data, instance=entry)
        self.assertFalse(form.is_valid())

        # Check that the suspended user can not be added because his balance would be below 0
        entry = DiningEntryUser(dining_list=self.dining_list, created_by=self.active_user)
        form = DiningEntryUserCreateForm(form_data, instance=entry)
        self.assertFalse(form.is_valid())

        # increase the suspended users balance
        FixedTransaction.objects.create(source_association=self.association,
                                        target_user=self.suspended_user,
                                        amount=2)

        # Check that suspended users can add himself
        entry = DiningEntryUser(dining_list=self.dining_list, created_by=self.suspended_user)
        form = DiningEntryUserCreateForm(form_data, instance=entry)
        self.assertTrue(form.is_valid())

        # Check that suspended users can be added
        entry = DiningEntryUser(dining_list=self.dining_list, created_by=self.active_user)
        form = DiningEntryUserCreateForm(form_data, instance=entry)
        self.assertTrue(form.is_valid())

        # Check that suspended user can not add other users
        form_data = {'user': self.third_user.pk}
        entry = DiningEntryUser(dining_list=self.dining_list, created_by=self.suspended_user)
        form = DiningEntryUserCreateForm(form_data, instance=entry)
        self.assertFalse(form.is_valid())

        # Check that suspended users can not add externals
        form_data = {'name': "guest"}
        entry = DiningEntryExternal(form_data,
                                    user=self.suspended_user,
                                    dining_list=self.dining_list,
                                    created_by=self.suspended_user)
        form = DiningEntryExternalCreateForm(form_data, instance=entry)
        self.assertFalse(form.is_valid())

    def test_add_user_w_unlimited_association(self):
        # Set up the association without limits
        association_2 = Association.objects.create(name="Financeers", has_min_exception=True)
        membership = UserMembership.objects.create(related_user=self.suspended_user, association=association_2, is_verified=True,
                                      verified_on=timezone.now())

        form_data = {'user': self.suspended_user.pk}

        # Check that the suspended user can not add himself because his balance would be below 0
        entry = DiningEntryUser(dining_list=self.dining_list, created_by=self.suspended_user)
        form = DiningEntryUserCreateForm(form_data, instance=entry)
        self.assertTrue(form.is_valid())

        # Check that the suspended user can not be added because his balance would be below 0
        entry = DiningEntryUser(dining_list=self.dining_list, created_by=self.active_user)
        form = DiningEntryUserCreateForm(form_data, instance=entry)
        self.assertTrue(form.is_valid())

        # Remove the association to prevent any testing order conflicts
        membership.delete()
        association_2.delete()

    def test_comment(self):
        form_data = {'message': "This should not be commented"}

        # Check that the user can not add comments
        form = DiningCommentForm(self.suspended_user, self.dining_list, data=form_data)
        self.assertFalse(form.is_valid())
