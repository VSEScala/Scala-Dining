from django.test import TestCase

from userdetails.forms import RegisterUserForm
from userdetails.models import Association


class RegisterUserFormTestCase(TestCase):
    def test_save_memberships(self):
        """Tests membership creation during form save."""
        a1 = Association.objects.create(name="a1")
        Association.objects.create(name="a2")
        form = RegisterUserForm(
            {
                "first_name": "Test",
                "last_name": "User",
                "username": "user",
                "email": "user@localhost",
                "password1": "yda7yum7MDV0ncw-hmw",
                "password2": "yda7yum7MDV0ncw-hmw",
                "associations": [a1],
            }
        )
        self.assertTrue(form.is_valid())
        user = form.save()
        memberships = list(user.usermembership_set.all())
        self.assertEqual(1, len(memberships))
        self.assertEqual(user, memberships[0].related_user)
        self.assertEqual(a1, memberships[0].association)
        self.assertTrue(memberships[0].is_pending())
