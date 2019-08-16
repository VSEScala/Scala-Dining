from abc import abstractmethod
from django.conf import settings
from django.core.mail import get_connection, EmailMessage, EmailMultiAlternatives
from django.template.loader import get_template, TemplateDoesNotExist


class AbstractNotification(object):
    """ Controls who need to be informed in a certain event

    Given a certain event (e.g. user is removed from dining list) determines who need to be informed
    and in what way. Then delegates the information to the relevant message constructor classes

    Attributes:
        mail_construction_class: the class that handles the mail construction and sending

    """
    mail_construction_class = None

    def notify(self):
        """ Notify all involved in the event of the invent """
        recipients = self.get_recipients()

        # Ensure that the recipients are of a queryset
        if recipients is settings.AUTH_USER_MODEL:
            settings.AUTH_USER_MODEL.objects.filter(pk=recipients.pk)

        if recipients is None:
            return

        mailed_recipients = self.filter_for_mailing(recipients)
        self.inform_through_mail(mailed_recipients)

    @abstractmethod
    def get_recipients(self):
        """ Fetches the recipients that need to be informed.

        Retrieves rows pertaining to the given keys from the Table instance
        represented by big_table.  Silly things may happen if
        other_silly_variable is not None.

        Returns:
            Any of the following three options:
            A Queryset of users (possibly empty)
            A single user
            None

        Raises:
            IOError: An error occurred accessing the bigtable.Table object.
        """
        return NotImplementedError()

    def get_event_data(self):
        """ Constructs the message data given to each message type

        Possible basic key-pairs are:
        active_user: The user who initiated the effect
        related_obj: The related object related with the event
        subject: The subject of the notiffcation (if supported)
        """
        return {}

    @abstractmethod
    def filter_for_mailing(self, recipients):
        """ Filters a given queryset on the users who want to receive the notification as a

        This method is abstract instead of returning the recipients to prevent casual mail implementation resulting
        in unwanted e-mail complaints.

        Args:
            recipients: A queryset of Users.

        Returns:
            A queryset of users who want to receive the notification as mail
        """
        raise NotImplementedError()

    def inform_through_mail(self, recipients):
        """ Informs the users through mail

        Creates an object of Mail defined in the mail_construction_class

        :param recipients:
        :return:
        """
        event_data = self.get_event_data()

        self.mail_construction_class(**event_data).send(recipients)


class AbstractMessage(object):
    """ Abstract shell for the means to send a notification

    This class, and it's children is responsible for constructing and sending the notifications through
    their respective means. It is sort of the View class of notifications.

    Methods:
        construct: constructs the message
        send: sends the message
    """

    def __init__(self, **event_data):
        """ Initialises the message

        Args:
            event_data: A dictionary of event data to get information from
        """
        self.construct(**event_data)

    @abstractmethod
    def construct(self, **event_data):
        """ Construct the message

        Args:
            event_data: A dictionary of event data to get information from
        """
        raise NotImplementedError()

    @abstractmethod
    def send(self, recipients):
        """ Sends the constructed message to the defined recipients

        Args:
            recipients: The recipients who the message needs to be send to
        """


class Mail(AbstractMessage):
    """ Constructs and sends mails

    Acts in a similar way as View, except instead constructs mail layouts

    """
    message_body = ""

    def construct(self, message="", **event_data):
        self.message_body = message
        if 'subject' in event_data:
            self.subject = event_data.pop('subject')
        else:
            try:
                self.subject
            except AttributeError:
                raise KeyError("No subject was present, did you forget to include it in the event data?")

    def get_as_django_email_message(self, subject, recipient, connection):
        """ Creates a django message object with the required information

        Args:
            subject: The subject of the mail
            recipient: The recipient of the mail
            connection: the used connection

        Returns: An EmailMessage instance

        """

        # Personalise the message with a custom adress call
        preamble = "Dear {user}\n"
        preamble = preamble.format(user=recipient.first_name)
        message = preamble + self.message_body

        to = [recipient]

        return EmailMessage(subject=subject,
                            body=message,
                            to=to,
                            connection=connection)

    def send(self, recipients):

        # Open a connection to send the mail to all recipients in a single run
        connection = get_connection()
        connection.open()

        if callable(self.subject):
            subject = self.subject()
        else:
            subject = self.subject

        for recipient in recipients:
            self.get_as_django_email_message(subject, recipient, connection) \
                .send(fail_silently=True)
        connection.close()


class TemplateMail(Mail):
    txt_template = None
    html_template = None
    target_user_format = 'target_user'

    @staticmethod
    def _get_mail_template(full_template_name):
        """ Gets the mail template of the given full name with the correct template loader

        Returns: a Template object

        """
        try:
            return get_template(full_template_name, using='EmailTemplates')
        except TemplateDoesNotExist:
            return None

    def construct(self, template_name=None, **event_data):
        super(TemplateMail, self).construct(**event_data)

        if template_name is None:
            try:
                template_name = self.template_name
            except AttributeError:
                raise KeyError("No template_name was defined in the class or construct parameters")


        # Get the templates
        txt_template = self._get_mail_template(template_name+".txt")
        if txt_template is None:
            raise KeyError("{t_name} does not exist as a template".format(t_name=template_name))
        html_template = self._get_mail_template(template_name+".html")

        self.event_data = event_data

        # Render the templates
        context_data = self.get_context_data()
        self.txt_template = txt_template.render(context_data)
        if html_template is not None:
            self.html_template = html_template.render(context_data)

    def get_context_data(self):
        """ Get the context data to render the template with.

        Automatically copies remaining attributes from event_data

        Returns: a dictionary of context data for the template

        """
        if self.event_data is None:
            return {}
        else:
            self.event_data

    def get_as_django_email_message(self, subject, recipient, connection):
        # Set up the Email template with the txt_template

        to = [recipient]

        body_personalised = self.txt_template.format(**{self.target_user_format: recipient.first_name})

        mail_obj = EmailMultiAlternatives(subject=subject, body=body_personalised, to=to, connection=connection)

        # Set up the html content in the mail
        if self.html_template is not None:
            html_personalised = self.html_template.format(**{self.target_user_format: recipient.first_name})
            mail_obj.attach_alternative(html_personalised, "text/html")

        # Send the mail
        return mail_obj









