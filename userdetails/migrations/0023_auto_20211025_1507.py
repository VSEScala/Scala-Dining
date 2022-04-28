# Generated by Django 3.2.8 on 2021-10-25 13:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userdetails', '0022_move_allergies'),
    ]

    operations = [
        migrations.RenameField(
            model_name='association',
            old_name='has_min_exception',
            new_name='allow_invoicing',
        ),
        migrations.AddField(
            model_name='association',
            name='invoicing_method',
            field=models.CharField(blank=True, help_text="How members will be invoiced. For instance 'Q-rekening' in the case of Quadrivium.", max_length=100),
        ),
    ]
