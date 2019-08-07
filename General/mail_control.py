from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import get_template, TemplateDoesNotExist
from django.conf import settings


class EmailTemplateMessage(EmailMultiAlternatives):
    """
    Renders emails from a given template
    """
    mail_source = settings.SEND_MAIL_FROM

    def __init__(self, *args, template_name=None, txt_template=None, html_template=None, context_data={}, **kwargs):
        # Check if the templates are given properly, if not, recompute them.
        if template_name is not None:
            if txt_template is not None:
                raise KeyError("Both a template and template name were given, only one of which was expected")
            txt_template, html_template = self.get_txt_html_templates(template_name)
        elif txt_template is None:
            raise KeyError("Template name is not defined")

        # remove body and from_email from kwarg arguments
        kwargs.pop('body', None)
        kwargs.pop('from_email', None)

        # Set up the Email template with the txt_template
        super(EmailTemplateMessage, self).__init__(*args, **kwargs,
                                                   body=txt_template.render(context_data),
                                                   from_email=self.mail_source)
        # Set up the html content in the mail
        if html_template is not None:
            content_html = html_template.render(context_data)
            self.attach_alternative(content_html, "text/html")

    @classmethod
    def get_txt_html_templates(cls, template_name):
        # Trim accidental file extensions
        for appendix in [".txt", ".html"]:
            if template_name.endswith(appendix):
                template_name = template_name[:, -len(appendix)]
        # Get the plain txt template
        try:
            txt_template = get_template(template_name+'.txt', using='EmailTemplates')
        except TemplateDoesNotExist:
            raise KeyError("{template}.txt does not exist, a plain version must exist".format(template=template_name))

        # Get the advanced html template
        try:
            html_template = get_template(template_name+'.html', using='EmailTemplates')
            return txt_template, html_template
        except TemplateDoesNotExist:
            return txt_template, None


def send_templated_mail(subject=None, template_name=None, context_data={}, recipient=None, fail_silently=False, **kwargs):
    if recipient is None:
        raise KeyError("No email target given. Please define the recipient")

    context_data['user'] = recipient
    to = [recipient.email]

    EmailTemplateMessage(subject=subject,
                         template_name=template_name,
                         context_data=context_data,
                         to=to, **kwargs).send(fail_silently=fail_silently)


def send_templated_mass_mail(subject=None, template_name=None, context_data={}, recipients=None, fail_silently=False, **kwargs):
    """
    Send a mass mail to all recipients with an EmailTemplateMessage as the message created
    :param subject: The email subject or header
    :param template_name: The name of the template
    :param context_data: the context data for the mail
    :param recipients: The queryset of users
    :param fail_silently: Whether an error needs to be created when sending fails
    :param kwargs: additional EmailTemplateMessage arguments
    """

    # Get the templates
    txt_template, html_template = EmailTemplateMessage.get_txt_html_templates(template_name)

    # Open the connection
    connection = get_connection()
    connection.open()

    for recipient in recipients:
        # Set the user in the context data
        context_data['user'] = recipient
        to = [recipient.email]

        EmailTemplateMessage(subject=subject,
                             txt_template=txt_template,
                             html_template=html_template,
                             context_data=context_data,
                             to=to, **kwargs)\
            .send(fail_silently=fail_silently)

    connection.close()




