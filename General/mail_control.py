from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import TemplateDoesNotExist, get_template


def _render_and_send_mail(*args, txt_template=None, html_template=None, context_data={}, fail_silently=False, **kwargs):
    # Set up the Email template with the txt_template
    mail_obj = EmailMultiAlternatives(*args, **kwargs, body=txt_template.render(context_data))

    # Set up the html content in the mail
    if html_template is not None:
        content_html = html_template.render(context_data)
        mail_obj.attach_alternative(content_html, "text/html")

    # Send the mail
    mail_obj.send(fail_silently=fail_silently)


def _get_mail_templates(full_template_name):
    try:
        return get_template(full_template_name, using='EmailTemplates')
    except TemplateDoesNotExist:
        return None


def send_templated_mail(subject=None, template_name=None, context_data={}, recipient=None, **kwargs):
    if recipient is None:
        raise KeyError("No email target given. Please define the recipient")

    context_data['user'] = recipient
    to = [recipient.email]

    _render_and_send_mail(subject=subject,
                          txt_template=_get_mail_templates(template_name + ".txt"),
                          html_template=_get_mail_templates(template_name + ".html"),
                          context_data=context_data,
                          to=to, **kwargs)


def send_templated_mass_mail(subject=None, template_name=None, context_data={}, recipients=None, **kwargs):
    """Send a mass mail to all recipients with an EmailTemplateMessage as the message created.

    Args:
        subject: The email subject or header.
        template_name: The name of the template.
        context_data: The context data for the mail.
        recipients: The queryset of users.
        **kwargs: Additional EmailTemplateMessage arguments.
    """
    # Get the templates
    txt_template = _get_mail_templates(template_name + ".txt")
    html_template = _get_mail_templates(template_name + ".html")

    # Open the connection
    connection = get_connection()
    connection.open()

    for recipient in recipients:
        # Set the user in the context data
        context_data['user'] = recipient
        to = [recipient.email]

        _render_and_send_mail(subject=subject,
                              txt_template=txt_template,
                              html_template=html_template,
                              context_data=context_data,
                              to=to, **kwargs)
    connection.close()
