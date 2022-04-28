from django.contrib.sites.shortcuts import get_current_site
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.http import HttpRequest
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from userdetails.models import User


"""Note about HTML mails:

I'm not a big fan of HTML mails because they always look different in different
clients (GMail, Outlook, Thunderbird), it's hard to get them right and the
resulting HTML always looks messy. Instead I prefer text only, it looks a bit
more dull but is much easier to maintain and the mails are shorter. To
implement this, I made providing a HTML version optional in the function below.

-- Maarten
"""


def get_mail_context(recipient: User, extra_context: dict = None, request: HttpRequest = None):
    """Creates the context used in mail templates."""
    # This is how Django does it with their password reset email
    current_site = get_current_site(request)
    use_https = request.is_secure() if request else False
    protocol = 'https' if use_https else 'http'
    return {
        'domain': current_site.domain,
        'site_name': current_site.name,
        'user': recipient,
        'protocol': protocol,
        'site_uri': '{}://{}'.format(protocol, current_site.domain),
        **(extra_context or {}),
    }


def send_templated_mail(template_dir: str, recipients, context: dict = None, request=None):
    """Sends a mail using a template.

    Args:
        template_dir: The directory containing the email templates. They should
            be named body.html, body.txt and subject.txt.
        recipients: The recipient(s) for the message as User instances. Can be
            a list or QuerySet if you want to send the mail to multiple users,
            or a single User instance.
        context: Will be added to the context for the template, alongside the
            context returned by get_mail_context.
        request: The request is necessary for figuring out the full site URL
            and for running the standard context processors.
    """
    if isinstance(recipients, User):
        recipients = [recipients]

    messages = []
    for recipient in recipients:
        # Render templates
        context = get_mail_context(recipient, context, request)
        subject = render_to_string(template_dir + '/subject.txt', context=context, request=request).strip()
        # HTML is optional
        try:
            html_body = render_to_string(template_dir + '/body.html', context=context, request=request)
        except TemplateDoesNotExist:
            html_body = None
        text_body = render_to_string(template_dir + '/body.txt', context=context, request=request).strip()
        # Create message
        message = EmailMultiAlternatives(subject=subject, body=text_body, to=[recipient.email])
        if html_body:
            message.attach_alternative(html_body, 'text/html')
        messages.append(message)

    # Send messages
    mail.get_connection().send_messages(messages)
