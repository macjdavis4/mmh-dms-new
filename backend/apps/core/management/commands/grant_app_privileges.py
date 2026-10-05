"""Give the app's database user read/write access to the data, and nothing more.

Production migrations run as the database owner (DigitalOcean's `doadmin`),
so the tables belong to it. The app connects as a separate, limited user
(`mmh_app`) that can read and write rows but cannot change or drop tables.
Run after every migration (the deploy's migrate step does this); safe to repeat.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from psycopg import sql


class Command(BaseCommand):
    help = "Grant the app's database role row-level access to all tables."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("role", help="The app's database role, e.g. mmh_app")

    def handle(self, *args: Any, role: str, **opts: Any) -> None:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT current_user, EXISTS (SELECT 1 FROM pg_roles WHERE rolname = %s)", [role]
            )
            me, exists = cur.fetchone()  # type: ignore[misc]
            if not exists:
                raise CommandError(f"Database role {role!r} does not exist")
            if me == role:
                self.stdout.write(f"Already connected as {role}; nothing to grant.")
                return
            r = sql.Identifier(role)
            statements = [
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(r),
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}"
                ).format(r),
                sql.SQL(
                    "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {}"
                ).format(r),
                sql.SQL("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {}").format(r),
                # Tables created by later migrations get the same access.
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                ).format(r),
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}"
                ).format(r),
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO {}"
                ).format(r),
            ]
            for statement in statements:
                cur.execute(statement)
        self.stdout.write(self.style.SUCCESS(f"Granted row access on all tables to {role}."))
