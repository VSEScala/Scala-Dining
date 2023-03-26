"""This migration copies the data from the old work stats/external columns to the new (merged) columns."""

# Generated by Django 3.2.13 on 2022-12-25 12:02

from django.db import migrations


def forwards(apps, schema_editor):
    DiningEntryUser = apps.get_model("dining", "DiningEntryUser")
    DiningEntryExternal = apps.get_model("dining", "DiningEntryExternal")

    # We need a for loop instead of update() because update() cannot be used across multiple tables.

    # Help stats
    for obj in DiningEntryUser.objects.all():
        # This works because DiningEntryUser is a subclass of DiningEntry.
        #
        # The new stats reside in a different table (DiningEntry) than the _old attributes.
        obj.has_shopped = obj.has_shopped_old
        obj.has_cooked = obj.has_cooked_old
        obj.has_cleaned = obj.has_cleaned_old
        obj.save()

    # External name
    for obj in DiningEntryExternal.objects.all():
        obj.external_name = obj.name
        obj.save()


def backwards(apps, schema_editor):
    DiningEntry = apps.get_model("dining", "DiningEntry")
    DiningEntryUser = apps.get_model("dining", "DiningEntryUser")
    DiningEntryExternal = apps.get_model("dining", "DiningEntryExternal")
    DiningWork = apps.get_model("dining", "DiningWork")

    for obj in DiningEntry.objects.all():
        if obj.external_name:
            # https://stackoverflow.com/a/4065189/2373688
            #
            # Not very elegant.
            new = DiningEntryExternal(diningentry_ptr=obj)
            new.__dict__.update(obj.__dict__)
            new.name = obj.external_name
            new.save()
        else:
            new = DiningEntryUser(diningentry_ptr=obj)
            new.__dict__.update(obj.__dict__)
            new.has_shopped_old = obj.has_shopped
            new.has_cooked_old = obj.has_cooked
            new.has_cleaned_old = obj.has_cleaned
            new.save()


class Migration(migrations.Migration):
    dependencies = [
        ('dining', '0023_add_new_help_stats'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards, elidable=True)
    ]