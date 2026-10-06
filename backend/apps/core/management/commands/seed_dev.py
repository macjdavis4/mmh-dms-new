"""Demo data for local development, end-to-end tests and screenshots.

Refuses to run in staging or production. Safe to run repeatedly.
"""

from __future__ import annotations

import base64
from typing import Any

from axes.utils import reset as axes_reset
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.core.context import acting_as
from apps.core.models import FeatureFlag, SiteSettings
from apps.parts.demo import load_demo_parts, load_demo_stock
from apps.sales.demo import load_demo_quotes
from apps.service.demo import load_demo_plans, load_demo_work_orders
from apps.units.demo import load_demo_data

DEMO_PASSWORD = "Forklift-Demo-2026!"  # noqa: S105 - demo data, never in prod
# Fixed 2FA secret for the demo admin so end-to-end tests can compute codes.
# Demo only: seed_dev refuses to run in staging and production.
DEMO_TOTP_BASE32 = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
DEMO_TOTP_HEX = base64.b32decode(DEMO_TOTP_BASE32).hex()

USERS = [
    ("admin@mmh.test", "Pat", "Owner", Role.ADMIN, True),
    ("admin2@mmh.test", "Lee", "Partner", Role.ADMIN, True),
    ("newadmin@mmh.test", "Jordan", "Manager", Role.ADMIN, False),
    ("sales@mmh.test", "Casey", "Seller", Role.SALES, False),
    ("service@mmh.test", "Sam", "Wrench", Role.SERVICE, False),
    ("parts@mmh.test", "Alex", "Counter", Role.PARTS, False),
    ("viewer@mmh.test", "Robin", "Viewer", Role.READ_ONLY, False),
]

# Finished features: switched on in demo data even if an older seed left them off.
LIVE_FLAGS = [
    "customers-units",
    "batch-import",
    "service",
    "units-changing-hands",
    "sales",
    "parts",
    "parts-stock",
]

# Features still being built: created switched off.
FLAGS: list[tuple[str, str]] = []


class Command(BaseCommand):
    help = "Create demo users (one per role), feature flags and site settings."

    def handle(self, *args: Any, **opts: Any) -> None:
        if settings.APP_ENV in {"staging", "production"}:
            raise CommandError("seed_dev only runs in development and test environments.")
        with transaction.atomic(), acting_as(source="cli"):
            for email, first, last, role, with_totp in USERS:
                user = User.all_objects.filter(email__iexact=email).first()
                if user is None:
                    user = User(email=email)
                user.first_name, user.last_name, user.role = first, last, role
                user.is_active = True
                user.deleted_at = None
                user.set_password(DEMO_PASSWORD)
                user.save()
                if with_totp:
                    TOTPDevice.objects.update_or_create(
                        user=user,
                        name="Demo authenticator",
                        defaults={"key": DEMO_TOTP_HEX, "confirmed": True},
                    )
                else:
                    # Reset any 2FA set up during a previous test run.
                    for model in (TOTPDevice, StaticDevice):
                        for device in model.objects.filter(user=user, confirmed=True):
                            device.confirmed = False
                            device.save()
            # Tidy up throwaway users created by earlier end-to-end runs.
            demo_emails = {u[0] for u in USERS}
            for leftover in User.objects.filter(email__endswith="@mmh.test"):
                if leftover.email.lower() not in demo_emails:
                    leftover.soft_delete()
            for key, description in FLAGS:
                if not FeatureFlag.objects.filter(key=key).exists():
                    FeatureFlag.objects.create(key=key, description=description, enabled=False)
            for flag in FeatureFlag.objects.filter(key__in=LIVE_FLAGS, enabled=False):
                flag.enabled = True
                flag.save()
            axes_reset()  # clear sign-in lockouts left by earlier test runs
            site = SiteSettings.load()
            site.read_only_mode = False
            site.banner_message = ""
            site.save()
            load_demo_data()
            load_demo_work_orders()
            load_demo_plans()
            load_demo_quotes()
            load_demo_parts()
            load_demo_stock()
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {len(USERS)} users. Password: {DEMO_PASSWORD}")
        )
        self.stdout.write(f"admin@mmh.test has 2FA; authenticator secret {DEMO_TOTP_BASE32}")
