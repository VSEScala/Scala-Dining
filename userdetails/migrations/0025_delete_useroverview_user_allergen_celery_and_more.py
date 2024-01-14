# Generated by Django 5.0 on 2024-01-14 15:10

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("userdetails", "0024_add_short_association_name"),
    ]

    operations = [
        migrations.DeleteModel(
            name="UserOverview",
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_celery",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_crustaceans",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_egg",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_fish",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_gluten",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_lupin",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_milk",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_molluscs",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_mustard",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_nuts",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_peanuts",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_sesame",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_soya",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="allergen_sulphite",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="food_preferences",
            field=models.CharField(
                blank=True,
                help_text="Preferences like vegetarian or vegan.",
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="other_allergy",
            field=models.CharField(
                blank=True,
                help_text="If you have an other allergy not listed above, enter it here.",
                max_length=200,
            ),
        ),
    ]
