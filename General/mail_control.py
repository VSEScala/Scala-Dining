from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template, TemplateDoesNotExist
from django.conf import settings


class EmailTemplateMessage(EmailMultiAlternatives):
    """
    Renders emails from a given template
    """
    mail_source = settings.SEND_MAIL_FROM

    def __init__(self, *args, template_name=None, context_data={}, body=None, from_email=None, **kwargs):
        # Trim template .txt of .html incase this is
        if template_name is None:
            raise KeyError("Template name is not defined")

        # Trim accidental file extensions
        for appendix in [".txt", ".html"]:
            if template_name.endswith(appendix):
                template_name = template_name[:, -len(appendix)]

        try:
            template = get_template(template_name+'.txt', using='EmailTemplates')
            content_plain = template.render(context_data)
        except TemplateDoesNotExist:
            raise KeyError("{template}.txt does not exist, a plain version must exist".format(template=template_name))

        super(EmailTemplateMessage, self).__init__(*args, **kwargs,
                                                   body=content_plain,
                                                   from_email=self.mail_source)
        try:
            content_html = get_template(template_name+'.html', using='EmailTemplates').render(context_data)
            self.attach_alternative(content_html, "text/html")
        except TemplateDoesNotExist:
            pass