from django import forms
from django.core.exceptions import ValidationError
from django.test import TestCase

from utils.testing.form_test_utils import FormValidityMixin


class TestFormValidityMixin(FormValidityMixin, TestCase):
    class TestForm(forms.Form):
        """Fictive form for Form testing used in TestFormValidityMixin."""

        main_field = forms.CharField(required=False)
        fake_field = forms.CharField(required=False)

        def clean_main_field(self):
            if self.cleaned_data["main_field"] == "break_field":
                raise ValidationError("Test field exception", code="invalid_field")
            return self.cleaned_data["main_field"]

        def clean(self):
            # Use get function, a fail in clean_main_field removes the entry from cleaned_data
            if self.cleaned_data.get("main_field", "") == "break_form":
                raise ValidationError("Test form exception", code="invalid_form")
            return self.cleaned_data

    form_class = TestForm
    longMessage = False

    def raises_assertion_error(self, method, *args, **kwargs):
        if isinstance(method, str):
            method = self.__getattribute__(method)
        try:
            method(*args, **kwargs)
        except AssertionError as error:
            return error
        else:
            raise AssertionError(f"AssertionError not raised on {method.__name__}")

    def test_assert_has_field(self):
        # This should not raise an error
        self.assertHasField("main_field")
        # This should
        error = self.raises_assertion_error(self.assertHasField, "missing_field")
        self.assertEqual(
            error.__str__(),
            "{field_name} was not a field in {form_class_name}".format(
                field_name="missing_field",
                form_class_name="TestForm",
            ),
        )

    def test_assert_form_valid(self):
        # This should not raise an error
        self.assertFormValid({"main_field": "ok"})
        # This should
        error = self.raises_assertion_error(
            self.assertFormValid, {"main_field": "break_field"}
        )
        self.assertEqual(
            error.__str__(),
            "The form was not valid. At least one error was encountered: '{exception_text}' in '{location}'".format(
                exception_text="Test field exception", location="main_field"
            ),
        )

    def test_assert_form_has_error_in_field(self):
        self.assertFormHasError({"main_field": "break_field"}, "invalid_field")
        self.assertFormHasError(
            {"main_field": "break_field"}, "invalid_field", field="main_field"
        )

        # Error is in main_field not fake_field
        with self.assertRaises(AssertionError):
            self.assertFormHasError(
                {"main_field": "break_field"}, "invalid_form", field="fake_field"
            )

        # This next data raises an error, just not the one with this code
        with self.assertRaises(AssertionError):
            self.assertFormHasError(
                {"main_field": "break_field"}, "invalid_data", field="main_field"
            )

    def test_assert_form_has_error_in_form(self):
        self.assertFormHasError({"main_field": "break_form"}, "invalid_form")

        # Should raise AssertionError because the form contains no errors.
        error = self.raises_assertion_error(
            self.assertFormHasError, {"main_field": "break_nothing"}, "invalid_form"
        )
        self.assertEqual(error.__str__(), "The form contained no errors")

        # Error is not in main_field, but elsewhere
        error = self.raises_assertion_error(
            self.assertFormHasError,
            {"main_field": "break_form"},
            "invalid_form",
            field="main_field",
        )
        self.assertEqual(
            str(error),
            "Form did not contain an error with code 'invalid_form', with field=main_field.",
        )

        # Error code is not correct, but there is another error
        error = self.raises_assertion_error(
            self.assertFormHasError, {"main_field": "break_form"}, "invalid_field"
        )
        self.assertEqual(
            str(error),
            "Form did not contain an error with code 'invalid_field', with field=None.",
        )
