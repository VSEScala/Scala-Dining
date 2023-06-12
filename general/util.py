import copy

import django.forms


class SelectWithDisabled(django.forms.Select):
    """Widget that adds disabled options to the select.

    The enabled options provided using the ChoiceField or other input are not
    touched, these disabled options are simply added afterwards.
    """

    def __init__(self, disabled_choices=(), *args, **kwargs):
        """Constructor.

        Args:
            disabled_choices: Must be just like the choices parameter, i.e. a
                list or tuple of tuple pairs with (option_value, option_label).
        """
        super().__init__(*args, **kwargs)
        self.disabled_choices = disabled_choices

    def __deepcopy__(self, memo):
        obj = super().__deepcopy__(memo)
        obj.disabled_choices = copy.copy(self.disabled_choices)
        memo[id(self)] = obj
        return obj

    def optgroups(self, name, value, attrs=None):
        groups = super().optgroups(name, value, attrs)

        # Append disabled choices as singleton groups
        index = len(groups)
        for option_value, option_label in self.disabled_choices:
            option = self.create_option(
                name, option_value, option_label, False, index, attrs=attrs
            )
            # Modify option so that it is disabled
            option["attrs"]["disabled"] = "disabled"
            # Add option to group
            groups.append((None, [option], index))
            index += 1

        return groups
