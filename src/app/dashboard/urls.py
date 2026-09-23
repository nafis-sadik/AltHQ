"""URL routes for the dashboard app."""

from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("persona/new/", views.persona_edit, name="persona_new"),
    path("persona/create/", views.persona_create, name="persona_create"),
    path("api/persona/update/", views.persona_update, name="persona_update"),
    path("api/avatar/generate/", views.avatar_generate, name="avatar_generate"),
    path("api/sheets/upload/", views.sheet_upload, name="sheet_upload"),
    path("api/sheets/<str:sheet_id>/delete/", views.sheet_delete, name="sheet_delete"),
    path("sheets/<str:sheet_id>/image/", views.sheet_image, name="sheet_image"),
    path("avatar/", views.avatar, name="avatar"),
]
