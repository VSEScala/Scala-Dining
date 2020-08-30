from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from userdetails.models import User


def send_templated_mail(template_dir: str, recipients, context: dict = None):
    """Sends a mail using a template.

    Args:
        template_dir: The directory containing the email templates. They should
            be named body.html, body.txt and subject.txt.
        recipients: The recipient(s) for the message as User instances. Can be
            a list or QuerySet if you want to send the mail to multiple users,
            or a single User instance.
        context: Used as the template's context for rendering. The recipient is
            added with key 'user'.
    """
    if context is None:
        context = {}
    if isinstance(recipients, User):
        recipients = [recipients]

    messages = []
    for recipient in recipients:
        # Render templates
        context['user'] = recipient
        subject = render_to_string(template_dir + '/subject.txt', context=context).strip()
        html_body = render_to_string(template_dir + '/body.html', context=context)
        text_body = render_to_string(template_dir + '/body.txt', context=context)
        # Create message
        message = EmailMultiAlternatives(subject=subject, body=text_body, to=[recipient.email])
        message.attach_alternative(html_body, 'text/html')
        messages.append(message)

    # Send messages
    mail.get_connection().send_messages(messages)
