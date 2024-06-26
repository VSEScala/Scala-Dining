# Generated by Django 2.2 on 2019-05-08 00:30

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dining", "0008_auto_20190507_0112"),
    ]

    operations = [
        migrations.AddField(
            model_name="diningentry",
            name="created_by",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_dining_entries",
                to=settings.AUTH_USER_MODEL,
                null=True,
            ),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="diningdayannouncement",
            name="text",
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name="diningdayannouncement",
            name="title",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="diningentry",
            name="dining_list",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dining_entries",
                to="dining.DiningList",
            ),
        ),
        migrations.AlterField(
            model_name="diningentry",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterField(
            model_name="diningentryexternal",
            name="name",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="diningentryuser",
            name="added_by",
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="added_entry_on_dining",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="dininglist",
            name="association",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to="userdetails.Association",
            ),
        ),
        migrations.AlterField(
            model_name="dininglist",
            name="claimed_by",
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="dininglist_claimer",
                to=settings.AUTH_USER_MODEL,
            ),
            preserve_default=False,
        ),
    ]
