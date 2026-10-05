"""Migration operations that add database-level guards.

Usage in a migration:

    from apps.core.migration_ops import PreventHardDelete
    operations = [PreventHardDelete("customers_customer")]
"""

from __future__ import annotations

from django.db import migrations

_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION mmh_refuse_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% on table % is not allowed (%)', TG_OP, TG_TABLE_NAME, TG_ARGV[0]
        USING ERRCODE = 'restrict_violation';
END;
$$;
"""


def PreventHardDelete(table: str) -> migrations.RunSQL:  # noqa: N802 (reads like an operation)
    """Refuse DELETE on a soft-delete table. Rows are retired with deleted_at."""
    trigger = f"{table}_no_hard_delete"
    return migrations.RunSQL(
        sql=[
            _FUNCTION_SQL,
            f"CREATE TRIGGER {trigger} BEFORE DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION mmh_refuse_change('soft delete only');",
        ],
        reverse_sql=[f"DROP TRIGGER IF EXISTS {trigger} ON {table};"],
    )


def AppendOnly(table: str) -> migrations.RunSQL:  # noqa: N802
    """Refuse UPDATE and DELETE: the table is an append-only log or ledger."""
    trigger = f"{table}_append_only"
    return migrations.RunSQL(
        sql=[
            _FUNCTION_SQL,
            f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION mmh_refuse_change('append only');",
        ],
        reverse_sql=[f"DROP TRIGGER IF EXISTS {trigger} ON {table};"],
    )
