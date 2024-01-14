from django import template

from userdetails.allergens import ALLERGENS

register = template.Library()


@register.inclusion_tag(
    filename="snippets/allergens_checkboxes.html",
    takes_context=True,
)
def allergens_checkboxes(context):
    return {
        "allergens": ALLERGENS,
    }
