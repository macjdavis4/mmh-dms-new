"""The offline copy on phones and tablets is behind the `offline` feature
flag (on). Switching it off stops devices saving a copy; copies already
saved are wiped the next time the app reaches the server."""

from django.db import migrations


def add_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("core", "FeatureFlag")
    if not FeatureFlag.objects.filter(key="offline").exists():
        FeatureFlag.objects.create(
            key="offline", description="Phase 13: offline copy on devices", enabled=True
        )


class Migration(migrations.Migration):
    dependencies = [("ops", "0003_paper_backups"), ("core", "0003_cache_table")]

    operations = [migrations.RunPython(add_flag, migrations.RunPython.noop)]
