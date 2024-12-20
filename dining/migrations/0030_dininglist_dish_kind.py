# Generated by Django 5.0 on 2024-01-13 19:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dining", "0029_diningcomment_deleted_diningcomment_email_sent_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="dininglist",
            name="dish_kind",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Not specified"),
                    ("meat", "🍗 Contains meat"),
                    ("fish", "🐟 Contains fish"),
                    ("vegetarian", "🥕 Vegetarian"),
                    ("vegan", "🌿 Vegan"),
                ],
                max_length=20,
                verbose_name="kind of dish",
            ),
        ),
    ]
