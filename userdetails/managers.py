from django.db.models import Manager
from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    def get_by_natural_key(self, username):
        # Allow the use of id to lookup as well
        if isinstance(username, int):
            return self.get(id=username)

        return self.get(username=username)


class AssociationManager(Manager):
    def get_by_natural_key(self, slug):
        return self.get(slug=slug)
