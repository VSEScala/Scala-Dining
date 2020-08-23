from django.db import migrations
from django.apps import apps


# Code excerpts taken from https://github.com/manuelnaranjo/django-database-view
# Original code no longer works, produced internal reference errors
# Excerpts taken for working version


def drop_view(schema_editor, model):
    """Drops view if exists on the database."""
    sql = 'DROP VIEW IF EXISTS %(table)s;'
    args = {
        'table': schema_editor.quote_name(model._meta.db_table),
    }
    schema_editor.execute(sql % args, None)


def create_view(schema_editor, model):
    args = {
        'table': schema_editor.quote_name(model._meta.db_table),
        'definition': str(model.view()),
    }
    # Create the new view
    sql = 'CREATE VIEW %(table)s AS %(definition)s'
    schema_editor.execute(sql % args, None)


class CreateView(migrations.CreateModel):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        models = apps.get_app_config(app_label).models_module
        model = getattr(models, self.name)

        # Drop any table with the same name
        drop_view(schema_editor, model)

        # Create the view
        create_view(schema_editor, model)

    def database_backwards(self, app_label, schema_editor, from_state, to):
        model = from_state.apps.get_model(app_label, self.name)
        drop_view(schema_editor, model)


class DeleteView(migrations.DeleteModel):

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.name)
        drop_view(schema_editor, model)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        models = apps.get_app_config(app_label).models_module
        model = getattr(models, self.name)

        # Ensure there is no view with this name
        drop_view(schema_editor, model)

        # Create the view
        create_view(schema_editor, model)
