# Generated by Django 2.2 on 2019-05-13 19:04

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('dining', '0014_auto_20190513_1505'),
    ]

    operations = [
        migrations.AddField(
            model_name='dininglist',
            name='main_contact',
            field=models.ForeignKey(blank=True, help_text='Is shown on the dining list. If not specified, all owners are shown.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='main_contact_dining_lists', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='dininglist',
            name='owners',
            field=models.ManyToManyField(help_text='Owners can manage the dining list. Board members can always manage the dining list even if they are not an owner.', related_name='owned_dining_lists', to=settings.AUTH_USER_MODEL),
        ),
    ]