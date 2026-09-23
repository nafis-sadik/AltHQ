"""URL routes for the dashboard app."""

from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("agents/switch/", views.agent_switch, name="agent_switch"),
    path("events/", views.event_log, name="event_log"),
    path("api/events/create/", views.event_node_create, name="event_node_create"),
    path("api/events/<str:node_id>/edit/", views.event_node_edit, name="event_node_edit"),
    path("api/events/<str:node_id>/delete/", views.event_node_delete, name="event_node_delete"),
    path(
        "api/events/<str:node_id>/messages/create/",
        views.event_message_create,
        name="event_message_create",
    ),
    path("api/messages/<str:message_id>/edit/", views.message_edit, name="message_edit"),
    path("api/messages/<str:message_id>/move/", views.message_move, name="message_move"),
    path("api/messages/<str:message_id>/delete/", views.message_delete, name="message_delete"),
    path("persona/new/", views.persona_edit, name="persona_new"),
    path("persona/create/", views.persona_create, name="persona_create"),
    path("api/persona/update/", views.persona_update, name="persona_update"),
    path("api/avatar/generate/", views.avatar_generate, name="avatar_generate"),
    path("api/sheets/upload/", views.sheet_upload, name="sheet_upload"),
    path("api/sheets/<str:sheet_id>/delete/", views.sheet_delete, name="sheet_delete"),
    path("sheets/<str:sheet_id>/image/", views.sheet_image, name="sheet_image"),
    path("avatar/", views.avatar, name="avatar"),
]
