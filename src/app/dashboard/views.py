"""Thin Django view adapters that dispatch to the domain controllers.

Each adapter is a one-line delegate to a method on the appropriate controller
obtained from the IoC container. They enforce the HTTP verb contract; every
controller method contains zero business rules.
"""

from django.views.decorators.http import require_GET, require_http_methods, require_POST

from agent_dashboard.container import container


# ---------------------------------------------------------------------------
# Persona domain (PersonaController)
# ---------------------------------------------------------------------------


@require_GET
def index(request):
    """Serve the SSR persona dashboard page."""
    return container.persona_controller().get_dashboard(request)


@require_GET
def persona_new(request):
    """Serve the SSR persona creation form page."""
    return container.persona_controller().get_new_persona(request)


@require_GET
def agents(request):
    """Serve the SSR agent browser and active-agent selection page."""
    return container.persona_controller().get_agents(request)


@require_POST
def agent_switch(request):
    """Persist the requested agent as active and return to the chosen page."""
    return container.persona_controller().post_agent_switch(request)


@require_POST
def agent_set_active(request, agent_id: str):
    """Set the requested agent as the only persisted active agent."""
    return container.persona_controller().post_set_active(request, agent_id)


@require_http_methods(["GET", "POST"])
def persona_collection(request):
    """Collection route: GET lists personas, POST creates a new persona."""
    controller = container.persona_controller()
    if request.method == "POST":
        return controller.post_create(request)
    return controller.get_personas(request)


@require_http_methods(["GET", "PUT"])
def persona_detail(request, agent_id: str):
    """Detail route: GET returns a persona, PUT updates an existing persona."""
    controller = container.persona_controller()
    if request.method == "PUT":
        return controller.put_update(request, agent_id)
    return controller.get_persona(request, agent_id)


@require_GET
def avatar(request):
    """Serve the selected persona's profile picture or placeholder."""
    return container.persona_controller().get_avatar(request)


@require_POST
def avatar_generate(request):
    """Kick off profile picture generation for the selected agent."""
    return container.persona_controller().post_generate_avatar(request)


@require_POST
def sheet_upload(request):
    """Store an uploaded character reference sheet for the selected agent."""
    return container.persona_controller().post_upload_sheet(request)


@require_http_methods(["DELETE"])
def sheet_delete(request, sheet_id: str):
    """Remove a character reference sheet and its stored file."""
    return container.persona_controller().delete_sheet(request, sheet_id)


@require_GET
def sheet_image(request, sheet_id: str):
    """Serve the stored bytes of a reference sheet image."""
    return container.persona_controller().get_sheet_image(request, sheet_id)


# ---------------------------------------------------------------------------
# Line of Truth domain (EventLogController)
# ---------------------------------------------------------------------------


@require_GET
def event_log(request):
    """Serve the SSR Line of Truth page for the selected agent."""
    return container.event_log_controller().get_event_log(request)


@require_POST
def event_node_collection(request):
    """Create a new timeline node for the selected agent."""
    return container.event_log_controller().post_create_node(request)


@require_http_methods(["PUT", "DELETE"])
def event_node_detail(request, node_id: str):
    """Update or delete one timeline node."""
    controller = container.event_log_controller()
    if request.method == "DELETE":
        return controller.delete_node(request, node_id)
    return controller.put_update_node(request, node_id)


@require_POST
def event_message_collection(request, node_id: str):
    """Add a message to a node with an optional user-supplied conversation time."""
    return container.event_log_controller().post_create_message(request, node_id)


@require_http_methods(["PUT", "DELETE"])
def message_detail(request, message_id: str):
    """Update or delete one message."""
    controller = container.event_log_controller()
    if request.method == "DELETE":
        return controller.delete_message(request, message_id)
    return controller.put_update_message(request, message_id)


@require_http_methods(["PUT"])
def message_move(request, message_id: str):
    """Move a message within its node or to another node."""
    return container.event_log_controller().put_move_message(request, message_id)