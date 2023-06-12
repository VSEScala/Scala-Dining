# flake8: noqa: N802


class FormValidityMixin:
    """A mixin for TestCase classes designed to add form functionality."""

    form_class = None

    def get_form_kwargs(self, **kwargs):
        return kwargs

    def build_form(self, data, form_class=None, **kwargs):
        """Builds the form, form_class can overwrite the default class attribute form_class."""
        if form_class is None:
            form_class = self.form_class
        return form_class(data=data, **self.get_form_kwargs(**kwargs))

    def assertHasField(self, field_name):
        """Asserts that the form has a field with the given name.

        Raises:
            AssertionError if not asserted, otherwise nothing.
        """
        form = self.build_form({})
        message = f"{field_name} was not a field in {form.__class__.__name__}"
        # This method is provided by the TestCase class.
        self.assertIn(field_name, form.fields, msg=message)

    def assertFormValid(self, data, form_class=None, **kwargs):
        """Asserts that the form is valid, otherwise raises AssertionError mentioning the form error.

        Args:
            data: The form data.
            form_class: The form class, defaults to self.form_class.
            kwargs: Any form init kwargs not defined in self.build_form().
        """
        form = self.build_form(data, form_class=form_class, **kwargs)

        if not form.is_valid():
            fail_message = (
                "The form was not valid. At least one error was encountered: "
            )

            invalidation_errors = form.errors.as_data()
            error_key = list(invalidation_errors.keys())[0]
            invalidation_error = invalidation_errors[error_key][0]
            fail_message += f"'{invalidation_error.message}' in '{error_key}'"
            raise AssertionError(fail_message)
        return form

    def assertFormHasError(self, data, code, form_class=None, field=None, **kwargs):
        """Asserts that a form with the given data invalidates on a certain error.

        Args:
            data: The form data.
            code: The 'code' of the ValidationError.
            form_class: The form class, defaults to self.form_class.
            field: The field on which the ValidationError needs to be, set to '__all__' if it's not a specific field.
                Leave empty if not relevant.
            kwargs: Any form init kwargs not defined in self.build_form().
        """
        form = self.build_form(data, form_class=form_class or self.form_class, **kwargs)

        if form.is_valid():
            raise AssertionError("The form contained no errors")

        # Extract the applicable ValidationError instances.
        if field:
            errors = form.errors.as_data().get(field, [])
        else:
            # Each value in form.errors is a list of ValidationError instances. We flatten this list here.
            errors = [
                item for sublist in form.errors.as_data().values() for item in sublist
            ]

        # Verify that we have an error AND that all errors have the correct code.
        if not errors or not all((e.code == code for e in errors)):
            raise AssertionError(
                f"Form did not contain an error with code '{code}', with field={field}."
            )
