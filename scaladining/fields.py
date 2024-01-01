"""Custom form fields."""

from django import forms


class DateTimeControlInput(forms.DateTimeInput):
    """See DateTimeControlField."""

    input_type = "datetime-local"

    def format_value(self, value):
        # The value given seems to be naive. If it wasn't, we would need to
        # make it naive first.
        return value.strftime("%Y-%m-%dT%H:%M")


class DateTimeControlField(forms.DateTimeField):
    """Field for input type datetime-local.

    The field requires a very specific format for the value attribute. This
    subclass sets the formatted value and the input format correctly.

    See: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/input/datetime-local
    """

    input_formats = ("%Y-%m-%dT%H:%M",)
    widget = DateTimeControlInput
