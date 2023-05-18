# Totally taken from https://github.com/frnhr/django-concurrenflict
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

        initial.setdefault("date_end", timezone.now())
        initial.setdefault(
            "date_start", initial["date_end"] - timezone.timedelta(days=365)
        )

        super().__init__(*args, initial=initial, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        date_start = cleaned_data.get("date_start")
        date_end = cleaned_data.get("date_end")
        if date_start and date_end and date_start > date_end:
            raise ValidationError(
                "The end date is further in the past than the starting date"
            )
        return cleaned_data


class ConcurrenflictFormMixin:
    """Compares model instances between requests.

    Compares first at form render, then upon submit but before save (i.e. on
    clean). If the model instances are different, the Form fails validation and
    displays what has been changed.
    """

    concurrenflict_field_name = "concurrenflict_initial"
    _concurrenflict_json_data = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.concurrenflict_field_name] = forms.CharField(
            widget=forms.HiddenInput, label="", required=False
        )
        instance = kwargs.get("instance", None)
        if instance:
            self._concurrenflict_json_data = serializers.serialize("json", [instance])
            self.fields[
                self.concurrenflict_field_name
            ].initial = self._concurrenflict_json_data

    def clean(self):  # noqa: C901
        # This function is too complex and ugly, should just get rid of it
        cleaned_data = super().clean()
        json_at_get = self.cleaned_data[self.concurrenflict_field_name]
        del self.cleaned_data[self.concurrenflict_field_name]
        json_at_post = self._concurrenflict_json_data
        # we want to keep using the initial data set in __init__()
        self.data = self.data.copy()
        self.data[
            self.add_prefix(self.concurrenflict_field_name)
        ] = self._concurrenflict_json_data
        have_diff = False

        # if json_at_post is None then this is an add() rather than a change(), so
        # there's no old record that could have changed while this one was being worked on
        if json_at_post and json_at_get and (json_at_post != json_at_get):
            json_data_before = json.loads(json_at_get)
            json_data_after = json.loads(json_at_post)

            serial_data_before = next(serializers.deserialize("json", json_at_get))
            model_before = serial_data_before.object
            m2m_before = serial_data_before.m2m_data
            serial_data_after = next(serializers.deserialize("json", json_at_post))
            model_after = serial_data_after.object
            m2m_after = serial_data_after.m2m_data

            fake_form = self.__class__(instance=model_after, prefix="concurrenflict")

            for field in list(model_before._meta.fields) + list(m2m_before.keys()):
                try:
                    key = field.name
                except AttributeError:
                    key = field  # m2m_before is dict, model._meta.fields is list of Fields
                if key == self.concurrenflict_field_name:
                    continue
                if key not in fake_form.fields.keys():
                    continue
                json_value_before = json_data_before[0]["fields"].get(key, None)
                json_value_after = json_data_after[0]["fields"].get(key, None)
                if json_value_after != json_value_before:
                    # value_before = getattr(model_before, key, m2m_before.get(key))
                    value_after = getattr(model_after, key, m2m_after.get(key, ""))
                    have_diff = True
                    # fake_form.data[key] = value_after
                    # js_fix = '''
                    # <script type="text/javascript">
                    #     (function($){
                    #         $(function(){
                    #             $('[name^="%(html_name)s"]').attr('disabled', 'disabled').attr('readonly', 'readonly');
                    #             $('#add_id_%(html_name)s').remove();
                    #         });
                    #     })(window.jQuery || django.jQuery);
                    # </script>
                    # ''' % {'html_name': fake_form[key].html_name}

                    if key in m2m_after:
                        value_after_string = ", ".join(
                            [str(v) for v in value_after.all()]
                        )
                    else:
                        value_after_string = str(value_after)
                    # temp_field = fake_form[key]
                    msg = mark_safe(
                        "This field has been changed by someone else to: %s"
                        % (value_after_string,)
                    )
                    self.add_error(key, msg)

                    # These fields are no longer valid. Remove them from the
                    # cleaned data. As if that has any effect...
                    if key in cleaned_data:
                        del cleaned_data[key]

        if have_diff:
            self.add_error(
                NON_FIELD_ERRORS,
                "The data has been changed by someone else since you started editing it",
            )

        return cleaned_data
