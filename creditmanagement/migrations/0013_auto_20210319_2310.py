# Generated by Django 3.1.7 on 2021-03-19 22:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('creditmanagement', '0012_auto_20200824_0135'),
    ]

    operations = [
        migrations.AlterField(
            model_name='account',
            name='special',
            field=models.CharField(choices=[('kitchen_cost', 'Kitchen cost')], default=None, max_length=30, null=True, unique=True),
        ),
    ]
