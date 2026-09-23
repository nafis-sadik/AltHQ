"""Root URL configuration for the agent dashboard."""

from django.urls import include, path

urlpatterns = [
    path("", include("dashboard.urls")),
]
