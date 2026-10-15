"""Emergency: remove someone's two-factor devices (lost phone, no recovery codes).

    sudo -u deploy /opt/mmh/current/manage.sh reset_2fa person@maine-material.com

They are signed out everywhere and set up two-factor again at their next sign-in. Recorded in the
audit log. Normally an admin does this from Users -> Reset two-factor.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.devices import end_sessions, remove_two_factor_devices
from apps.accounts.models import User
from apps.core.context import acting_as
from apps.core.models import AuditLog


class Command(BaseCommand):
    help = "Remove a user's two-factor devices so they can set it up again."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("email")

    def handle(self, *args: Any, email: str, **opts: Any) -> None:
        user = User.objects.filter(email__iexact=email.strip()).first()
        if user is None:
            raise CommandError(f"No active user with email {email}")
        with transaction.atomic(), acting_as(source="cli"):
            remove_two_factor_devices(user)
            end_sessions(user)
            AuditLog.record(AuditLog.Action.TWO_FACTOR_DISABLED, user, after={"by": "command line"})
        self.stdout.write(self.style.SUCCESS(f"Two-factor reset for {user.email}."))
