from django.db import models



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
