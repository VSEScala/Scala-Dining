"""Custom form fields."""

import datetime

from django import forms
from django.utils.timezone import is_aware


class DateTimeControlInput(forms.DateTimeInput):
    """See DateTimeControlField."""

    input_type = "datetime-local"

    def format_value(self, value):
        """This method formats the value for output on the form field.

        The argument might be a datetime when it comes from the model. Or a string if
        it comes from POST data.
        """
        if isinstance(value, datetime.datetime):
            if is_aware(value):
                raise RuntimeError("Unexpected datetime value")
            return value.strftime("%Y-%m-%dT%H:%M")
        elif isinstance(value, str):
            return value
        else:
            raise RuntimeError("Unexpected value type")


class DateTimeControlField(forms.DateTimeField):
    """Field for input type datetime-local.

    The field requires a very specific format for the value attribute. This
    subclass sets the formatted value and the input format correctly.

    See: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/datetime-local
    """

    input_formats = ("%Y-%m-%dT%H:%M",)
    widget = DateTimeControlInput
