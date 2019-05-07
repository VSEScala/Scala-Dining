from django.forms.widgets import NumberInput


class SearchWidget(NumberInput):
    """
    Displays a custom search widget for a given query
    """
    template_name = 'general/widget_search_select.html'

    def get_context(self, *args, **kwargs):
        context = super(SearchWidget, self).get_context(*args, **kwargs)
        print("Context Get")
        context['widget']['queryset'] = self.queryset
        return context

    def __init__(self, *args, queryset=None, **kwargs):
        self.queryset = queryset
        super(SearchWidget, self).__init__(*args, **kwargs)