# Generated by Django 2.1.3 on 2019-02-07 14:10

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("userdetails", "0004_user_external_link"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usermembership",
            name="created_on",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name="usermembership",
            name="verified_on",
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
