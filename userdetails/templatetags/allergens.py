from django import template

from userdetails.allergens import ALLERGENS

register = template.Library()


@register.inclusion_tag(
    filename="snippets/allergens_checkboxes.html",
    takes_context=True,
)
def allergens_checkboxes(context):
    if "form" in context:
        fields = (context["form"][allergen.model_field] for allergen in ALLERGENS)
    else:
        fields = (None for _ in ALLERGENS)
    return {
        "allergens": zip(ALLERGENS, fields),
    }


@register.filter
def get_allergens(user):
    """Returns a list of allergens for a given user."""
    return [a for a in ALLERGENS if getattr(user, a.model_field)]
