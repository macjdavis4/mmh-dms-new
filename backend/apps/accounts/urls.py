from django.urls import path

from . import views

urlpatterns = [
    path("csrf", views.CsrfView.as_view(), name="auth-csrf"),
    path("me", views.MeView.as_view(), name="auth-me"),
    path("login", views.LoginView.as_view(), name="auth-login"),
    path("login/verify", views.LoginVerifyView.as_view(), name="auth-login-verify"),
    path("logout", views.LogoutView.as_view(), name="auth-logout"),
    path("password", views.PasswordChangeView.as_view(), name="auth-password"),
    path("2fa/setup", views.TwoFactorSetupView.as_view(), name="auth-2fa-setup"),
    path("2fa/confirm", views.TwoFactorConfirmView.as_view(), name="auth-2fa-confirm"),
    path("2fa/disable", views.TwoFactorDisableView.as_view(), name="auth-2fa-disable"),
    path("2fa/recovery-codes", views.RecoveryCodesView.as_view(), name="auth-2fa-recovery"),
]
