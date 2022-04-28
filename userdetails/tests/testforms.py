from django.test import TestCase

from userdetails.forms import MembershipForm
from userdetails.models import User


class MembershipFormTestCase(TestCase):
    def test_at_least_one(self):
        """Tests that at least one association needs to be selected."""
        user = User.objects.create_user('test')
        form = MembershipForm(user, data={})
        # No associations selected, form should be invalid
        self.assertFalse(form.is_valid())
