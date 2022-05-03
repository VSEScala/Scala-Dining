from django.db.models import Manager
from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager):
    def get_by_natural_key(self, username):
        return self.get(username=username)


class AssociationManager(Manager):
    def get_by_natural_key(self, slug):
        return self.get(slug=slug)
