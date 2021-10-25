import json

from django import forms
from django.core import serializers
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.utils import timezone
from django.utils.safestring import mark_safe


class DateRangeForm(forms.Form):
    date_start = forms.DateField()
    date_end = forms.DateField()

    def __init__(self, *args, initial=None, **kwargs):
        if initial is None:
            initial = {}

        initial.setdefault('date_end', timezone.now())
        initial.setdefault('date_start', initial['date_end'] - timezone.timedelta(days=365))

        super().__init__(*args, initial=initial, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        date_start = cleaned_data.get('date_start')
        date_end = cleaned_data.get('date_end')
        if date_start and date_end and date_start > date_end:
            raise ValidationError("The end date is further in the past than the starting date")
        return cleaned_data


# Here stood the following earlier: https://github.com/frnhr/django-concurrenflict
