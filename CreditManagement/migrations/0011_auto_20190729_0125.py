# Generated by Django 2.1.5 on 2019-07-28 23:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('CreditManagement', '0010_auto_20190728_1551'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fixedtransaction',
            name='confirm_moment',
            field=models.DateTimeField(blank=True, default=None),
        ),
        migrations.AlterField(
            model_name='pendingtransaction',
            name='confirm_moment',
            field=models.DateTimeField(blank=True, default=None),
        ),
    ]