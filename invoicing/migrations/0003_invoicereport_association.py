# Generated by Django 3.2.8 on 2022-02-12 11:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('userdetails', '0031_alter_association_invoicing_method'),
        ('invoicing', '0002_auto_20220212_1226'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoicereport',
            name='association',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, to='userdetails.association'),
            preserve_default=False,
        ),
    ]