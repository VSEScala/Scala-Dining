from django.db import models
from django.conf import settings


# Create your models here.

class SiteUpdate(models.Model):
    """
    Contains setting related to the dining lists and use of the dining lists.
    """
    date = models.DateField(auto_now_add=True, unique=True)
    version = models.CharField(max_length=16, help_text="The current version", unique=True)
    title = models.CharField(max_length=140, unique=True)
    message = models.TextField()

    def __str__(self):
        return self.version + ": " + self.title


class AbstractVisitTracker(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract=True


class PageVisitTracker(AbstractVisitTracker):
    page = models.IntegerField()

    def __get_page_int__(self, page_name):
        """
        Returns the integer form for the type of page
        :param page_name: The page name
        :return: The integer number for the page
        """
        page_name = page_name.lower()
        if page_name == "updates":
            return 1
        if page_name == "rules":
            return 2

        return None

    @classmethod
    def get_latest_vistit(cls, page_name, user, update=False):
        latest_visit_obj = cls.objects.get_or_create(user=user, page=cls.__get_page_int__(page_name))[0]
        timestamp = last_visit.timestamp
        if update:
            last_visit.timestamp = timezone.now()
            last_visit.save()
        return timestamp