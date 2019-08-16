from General.notifications_base import TemplateMail, AbstractNotification


class TestNotification(AbstractNotification):
    """ A Notification class for test notifications, currently only implements mails.

    """
    mail_construction_class = TemplateMail

    def __init__(self, recipients):
        self.recipients = recipients

    def get_event_data(self):
        event_data = super(TestNotification, self).get_event_data()
        event_data['subject'] = "This is a test message title"
        event_data['template_name'] = 'general/testmail'
        return event_data

    def get_recipients(self):
        return self.recipients

    def filter_for_mailing(self, recipients):
        return recipients