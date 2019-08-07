from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import get_template, TemplateDoesNotExist


class EmailTemplateMessage(EmailMultiAlternatives):
    """
    Renders emails from a given template
    """

    def __init__(self, *args, txt_template=None, html_template=None, context_data={}, **kwargs):
        # remove body and from_email from kwarg arguments
        kwargs.pop('body', None)

        # Set up the Email template with the txt_template
        super(EmailTemplateMessage, self).__init__(*args, **kwargs,
                                                   body=txt_template.render(context_data))
        # Set up the html content in the mail
        if html_template is not None:
            content_html = html_template.render(context_data)
            self.attach_alternative(content_html, "text/html")


def get_mail_templates(full_template_name):
    try:
        return get_template(full_template_name, using='EmailTemplates')
    except TemplateDoesNotExist:
            return None


def send_templated_mail(subject=None, template_name=None, context_data={}, recipient=None, fail_silently=False, **kwargs):
    if recipient is None:
        raise KeyError("No email target given. Please define the recipient")

    context_data['user'] = recipient
    to = [recipient.email]

    EmailTemplateMessage(subject=subject,
                         txt_template=get_mail_templates(template_name+".txt"),
                         context_data=get_mail_templates(template_name+".html"),
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
    txt_template = get_mail_templates(template_name+".txt")
    html_template = get_mail_templates(template_name+".html")

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




