"""App configuration for the dashboard app."""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Django app config registering the dashboard application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"
    verbose_name = "Agent Dashboard"
