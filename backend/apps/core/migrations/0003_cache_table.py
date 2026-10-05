from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    call_command("createcachetable", database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [("core", "0002_db_guards")]

    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
