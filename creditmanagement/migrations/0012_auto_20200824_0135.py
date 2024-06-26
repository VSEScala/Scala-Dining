# Generated by Django 2.2.15 on 2020-08-23 23:35

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("creditmanagement", "0011_account_transaction"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="pendingdiningtransaction",
            name="source_association",
        ),
        migrations.RemoveField(
            model_name="pendingdiningtransaction",
            name="source_user",
        ),
        migrations.RemoveField(
            model_name="pendingdiningtransaction",
            name="target_association",
        ),
        migrations.RemoveField(
            model_name="pendingdiningtransaction",
            name="target_user",
        ),
        migrations.AddField(
            model_name="account",
            name="special",
            field=models.CharField(default=None, max_length=30, null=True, unique=True),
        ),
        migrations.DeleteModel(
            name="PendingDiningListTracker",
        ),
        # Added this managed=True manually, because in migration 8 the PendingDiningTransaction table was created and
        # afterwards set to managed=False. Due to this, it was physically created in the database and will remain there
        # if this isn't set back to managed=True.
        migrations.AlterModelOptions(
            name="PendingDiningTransaction",
            options={
                "managed": True,
            },
        ),
        migrations.DeleteModel(  # (This model had managed=False)
            name="PendingDiningTransaction",
        ),
    ]
