# Generated by Django 2.1.2 on 2018-10-16 15:36

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('Dining', '0001_initial'),
        ('UserDetails', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userdiningstats',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='userdiningsettings',
            name='user',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='dininglist',
            name='association',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='UserDetails.Association', unique_for_date='date'),
        ),
        migrations.AddField(
            model_name='dininglist',
            name='claimed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dininglist_claimer', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='dininglist',
            name='purchaser',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dininglist_purchaser', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='diningentryexternal',
            name='dining_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='Dining.DiningList'),
        ),
        migrations.AddField(
            model_name='diningentryexternal',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='added by (has cost responsibility)'),
        ),
        migrations.AddField(
            model_name='diningentry',
            name='added_by',
            field=models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_DEFAULT, related_name='added_entry_on_dining', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='diningentry',
            name='dining_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='Dining.DiningList'),
        ),
        migrations.AddField(
            model_name='diningentry',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='diningcommentviews',
            name='dining_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='Dining.DiningList'),
        ),
        migrations.AddField(
            model_name='diningcommentviews',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='diningcomments',
            name='dining_list',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='Dining.DiningList'),
        ),
        migrations.AddField(
            model_name='diningcomments',
            name='poster',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='DiningListComment',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
            },
            bases=('Dining.dininglist',),
        ),
    ]
