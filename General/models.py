from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail, send_mass_mail
from .mail_control import EmailTemplateMessage

# Create your models here.


class SiteUpdate(models.Model):
    """
    Contains setting related to the dining lists and use of the dining lists.
    """
    date = models.DateTimeField(auto_now_add=True, unique=True)
    title = models.CharField(max_length=140, unique=True)
    message = models.TextField()

    def __str__(self):
        return "{date}: {title}".format(date=self.date.strftime("%Y-%m-%d"), title=self.title)

    def mail_users(self):
        subject = "Scala Dining App Update: {title}".format(title=self.title)
        template = "general/update_broadcast"
        context = {}
        context['update'] = self.message

        from UserDetails.models import User
        for user in User.objects.filter(id=1):
            mail = EmailTemplateMessage(subject=subject,
                                        template_name=template,
                                        context_data=context,
                                        to=[user.email]).send()

    def outdated_mail_users(self):
        subject = "Scala Dining App Update: {title}".format(title=self.title)

        message_start = "Dear {name}, \nI'd like to inform you on a recent update on the Scala Dining App:"
        message_end = "-----------------\nI hope to have informed you well.\n \nScala Dining Mailbot"
        full_message = message_start + "\n\n" + self.message + "\n\n" + message_end

        mail_data = []

        from UserDetails.models import User
        for user in User.objects.all():
            personal_message = full_message.format(name=user.first_name)
            mail_data.append((subject, personal_message, settings.SEND_MAIL_FROM, [user.email]))

        send_mass_mail(mail_data)


class AbstractVisitTracker(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract=True


class PageVisitTracker(AbstractVisitTracker):
    page = models.IntegerField()

    @classmethod
    def __get_page_int__(cls, page_name):
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
    def get_latest_visit(cls, page_name, user, update=False):
        """
        Get the datetime of the latest visit.
        If there isn't one it either returns None, or the current time if update is set to True
        :param page_name: The name of the page
        :param user: The user visiting the page
        :param update:
        :return:
        """
        if update:
            latest_visit_obj = cls.objects.get_or_create(user=user, page=cls.__get_page_int__(page_name))[0]
        else:
            try:
                latest_visit_obj = cls.objects.get(user=user, page=cls.__get_page_int__(page_name))
            except cls.DoesNotExist:
                return None

        timestamp = latest_visit_obj.timestamp
        if update:
            latest_visit_obj.timestamp = timezone.now()
            latest_visit_obj.save()
        return timestamp