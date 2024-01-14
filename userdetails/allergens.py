from dataclasses import dataclass

"""
Sources:

* https://allergenen.sho-horeca.nl/
* https://www.voedingscentrum.nl/encyclopedie/allergenen.aspx
"""


@dataclass
class Allergen:
    model_field: str  # The field name on the User model
    name_en: str
    name_nl: str
    icon: str
    # description: str = None

    def get_value(self, user):
        return getattr(user, self.model_field)


ALLERGENS = [
    Allergen(
        model_field="allergen_gluten",
        name_en="Gluten",
        name_nl="Gluten",
        icon="allergens/gluten.png",
    ),
    Allergen(
        model_field="allergen_egg",
        name_en="Egg",
        name_nl="Ei",
        icon="allergens/egg.png",
    ),
    Allergen(
        model_field="allergen_fish",
        name_en="Fish",
        name_nl="Vis",
        icon="allergens/fish.png",
    ),
    Allergen(
        model_field="allergen_peanuts",
        name_en="Peanuts",
        name_nl="Pinda",
        icon="allergens/peanuts.png",
    ),
    Allergen(
        model_field="allergen_nuts",
        name_en="Nuts",
        name_nl="Noten",
        icon="allergens/nuts.png",
    ),
    Allergen(
        model_field="allergen_soya",
        name_en="Soya",
        name_nl="Soja",
        icon="allergens/soya.png",
    ),
    Allergen(
        model_field="allergen_milk",
        name_en="Milk",
        name_nl="Melk",
        icon="allergens/milk.png",
    ),
    Allergen(
        model_field="allergen_crustaceans",
        name_en="Crustaceans",
        name_nl="Schaaldieren",
        icon="allergens/crustaceans.png",
    ),
    Allergen(
        model_field="allergen_molluscs",
        name_en="Molluscs",
        name_nl="Weekdieren",
        icon="allergens/molluscs.png",
    ),
    Allergen(
        model_field="allergen_celery",
        name_en="Celery",
        name_nl="Selderij",
        icon="allergens/celery.png",
    ),
    Allergen(
        model_field="allergen_mustard",
        name_en="Mustard",
        name_nl="Mosterd",
        icon="allergens/mustard.png",
    ),
    Allergen(
        model_field="allergen_sesame",
        name_en="Sesame",
        name_nl="Sesamzaad",
        icon="allergens/sesame.png",
    ),
    Allergen(
        model_field="allergen_sulphite",
        name_en="Sulphite",
        name_nl="Sulfiet",
        icon="allergens/sulphite.png",
    ),
    Allergen(
        model_field="allergen_lupin",
        name_en="Lupin",
        name_nl="Lupine",
        icon="allergens/lupin.png",
    ),
]
