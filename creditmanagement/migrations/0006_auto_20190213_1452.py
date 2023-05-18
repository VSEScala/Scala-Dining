# Generated by Django 2.1.3 on 2019-02-13 13:52

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('creditmanagement', '0005_usercredit_view'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fixedtransaction',
            name='confirm_moment',
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='fixedtransaction',
            name='order_moment',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='pendingtransaction',
            name='confirm_moment',
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='pendingtransaction',
            name='order_moment',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
