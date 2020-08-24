from django.db.migrations import DeleteModel


class SafeDeleteModel(DeleteModel):
    """Blocks deletion operation when the table is not empty."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.name)
        if model.objects.exists():
            raise RuntimeError("Can't delete model, the table isn't empty")
        super().database_forwards(app_label, schema_editor, from_state, to_state)
