import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection


@pytest.mark.django_db
def test_app_role_gets_row_access_but_not_schema_changes() -> None:
    with connection.cursor() as cur:
        cur.execute("DROP ROLE IF EXISTS mmh_test_app")
        cur.execute("CREATE ROLE mmh_test_app NOLOGIN")
    try:
        call_command("grant_app_privileges", "mmh_test_app")
        with connection.cursor() as cur:
            cur.execute(
                "SELECT has_table_privilege('mmh_test_app', 'units_unit', 'SELECT,INSERT,UPDATE,DELETE'),"
                " has_table_privilege('mmh_test_app', 'units_unit', 'TRUNCATE'),"
                " has_schema_privilege('mmh_test_app', 'public', 'CREATE')"
            )
            rw, truncate, create = cur.fetchone()
        assert rw is True
        assert truncate is False
        assert create is False
    finally:
        with connection.cursor() as cur:
            cur.execute("DROP OWNED BY mmh_test_app")
            cur.execute("DROP ROLE mmh_test_app")


@pytest.mark.django_db
def test_unknown_role_is_an_error() -> None:
    with pytest.raises(CommandError, match="does not exist"):
        call_command("grant_app_privileges", "no_such_role")
