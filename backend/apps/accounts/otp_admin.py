"""Django admin sign-in with a 2FA code, refusing retired devices.

django-otp's admin form loads whichever device the form names and only checks
that it belongs to the user, not that it is still confirmed. A turned-off
authenticator (or old recovery codes) must never sign anyone in."""

from __future__ import annotations

from typing import Any

from django_otp.admin import OTPAdminAuthenticationForm, OTPAdminSite


class ConfirmedDeviceAdminAuthenticationForm(OTPAdminAuthenticationForm):
    def _chosen_device(self, user: Any) -> Any:
        device = super()._chosen_device(user)
        if device is not None and not getattr(device, "confirmed", False):
            return None
        return device


class ConfirmedDeviceOTPAdminSite(OTPAdminSite):
    login_form = ConfirmedDeviceAdminAuthenticationForm
