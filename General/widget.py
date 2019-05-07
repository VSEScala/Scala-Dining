from django.forms.widgets import NumberInput
from django.db.models import ObjectDoesNotExist


class SearchWidget(NumberInput):
    """
    Displays a custom search widget for a given query
    """
    template_name = 'general/widget_search_select.html'

    def get_context(self, *args, **kwargs):
        context = super(SearchWidget, self).get_context(*args, **kwargs)
        context['widget']['queryset'] = self.queryset
        # Check if the given contents are not empty
        # (if an error occurs during form submit, the string "None" can be passed)
        if context['widget']['value'] is not None:
            # Get the current value objects name
            try:
                context['widget']['value_name'] = self.queryset.get(id=int(context['widget']['value']))
            except ObjectDoesNotExist:
                pass

        return context

    def __init__(self, *args, queryset=None, **kwargs):
        self.queryset = queryset
        super(SearchWidget, self).__init__(*args, **kwargs)