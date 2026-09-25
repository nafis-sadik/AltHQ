"""URL routes for the dashboard app, mapped to the domain controllers."""

from django.urls import path

from dashboard import views

app_name = "dashboard"

urlpatterns = [
    # Persona domain (PersonaController)
    path("", views.index, name="index"),
    path("persona/new/", views.persona_new, name="persona_new"),
    path("agents/", views.agents, name="agents"),
    path("agents/switch/", views.agent_switch, name="agent_switch"),
    path("api/personas/", views.persona_collection, name="persona_api"),
    path("api/personas/<str:agent_id>/", views.persona_detail, name="persona_detail"),
    path(
        "api/agents/<str:agent_id>/set_active/",
        views.agent_set_active,
        name="agent_set_active",
    ),
    path("api/avatar/generate/", views.avatar_generate, name="avatar_generate"),
    path("avatar/", views.avatar, name="avatar"),
    path("api/sheets/", views.sheet_upload, name="sheet_upload"),
    path("api/sheets/<str:sheet_id>/", views.sheet_delete, name="sheet_delete"),
    path("sheets/<str:sheet_id>/image/", views.sheet_image, name="sheet_image"),
    # Line of Truth domain (EventLogController)
    path("events/", views.event_log, name="event_log"),
    path("api/events/", views.event_node_collection, name="event_node_collection"),
    path("api/events/<str:node_id>/", views.event_node_detail, name="event_node_detail"),
    path(
        "api/events/<str:node_id>/messages/",
        views.event_message_collection,
        name="event_message_collection",
    ),
    path("api/messages/<str:message_id>/", views.message_detail, name="message_detail"),
    path("api/messages/<str:message_id>/move/", views.message_move, name="message_move"),
]