# Generated by Django 2.1.5 on 2019-07-28 11:59

from decimal import Decimal

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dining', '0011_auto_20190508_1905'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dininglist',
            name='dining_cost',
            field=models.DecimalField(blank=True, decimal_places=2, default=None, max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.00'))], verbose_name='dinner cost per person'),
        ),
    ]
