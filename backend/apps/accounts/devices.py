"""Removing someone's 2FA devices.

Devices are deleted, not just marked unconfirmed: an unconfirmed device still
holds its secret key and recovery codes, and django-otp's admin sign-in and
session middleware will accept it. Deleting them also strips 2FA status from
every session that was verified with them. (These are django-otp's tables,
not business records; the change itself goes in the audit log.)"""

from __future__ import annotations

from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from .models import User


def remove_two_factor_devices(user: User) -> None:
    TOTPDevice.objects.filter(user=user).delete()
    StaticDevice.objects.filter(user=user).delete()  # cascades to the recovery codes


def end_sessions(user: User, *, keep: str | None = None) -> int:
    """Sign the person out everywhere (except the session key `keep`).

    Used when an admin resets someone's 2FA for a lost phone: otherwise
    whoever holds that phone's signed-in session could set up their own
    authenticator. There is no index from user to session, but a dealership
    has few sessions, so decoding each is fine."""
    from django.contrib.auth import SESSION_KEY
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    ended = 0
    for session in Session.objects.filter(expire_date__gt=timezone.now()).iterator():
        if session.session_key == keep:
            continue
        if str(session.get_decoded().get(SESSION_KEY)) == str(user.pk):
            session.delete()
            ended += 1
    return ended
