from typing import List

from django.contrib.sites.shortcuts import get_current_site
from django.core import mail
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.http import HttpRequest
from django.template.loader import render_to_string

from userdetails.models import User


def get_mail_context(
    recipient: User, extra_context: dict = None, request: HttpRequest = None
):
    """Creates the context used in mail templates."""
    # This is how Django does it with their password reset email
    current_site = get_current_site(request)
    use_https = request.is_secure() if request else False
    protocol = "https" if use_https else "http"
    return {
        "domain": current_site.domain,
        "site_name": current_site.name,
        "recipient": recipient,
        "protocol": protocol,
        "site_uri": "{}://{}".format(protocol, current_site.domain),
        **(extra_context or {}),
    }


def construct_templated_mail(
    template_dir: str, recipients, context: dict = None, request=None
) -> List[EmailMessage]:
    """Constructs email messages.

    See send_templated_mail() for an explanation of the arguments.
    """
    if isinstance(recipients, User):
        recipients = [recipients]

    messages = []
    for recipient in recipients:
        # Render templates
        local_context = get_mail_context(recipient, context, request)
        subject = render_to_string(
            template_dir + "/subject.txt", context=local_context, request=request
        ).strip()
        html_body = render_to_string(
            template_dir + "/body.html", context=local_context, request=request
        )
        text_body = render_to_string(
            template_dir + "/body.txt", context=local_context, request=request
        )
        # Create message
        message = EmailMultiAlternatives(
            subject=subject, body=text_body, to=[recipient.email]
        )
        message.attach_alternative(html_body, "text/html")
        messages.append(message)
    return messages


def send_templated_mail(
    template_dir: str, recipients, context: dict = None, request=None
):
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
    messages = construct_templated_mail(template_dir, recipients, context, request)
    mail.get_connection().send_messages(messages)
