"""Thin Django views for the persona dashboard; all logic delegates to Layer 2."""

from datetime import datetime, timezone
from urllib.parse import urlencode

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from agent_dashboard.container import container
from business.memory import MESSAGE_SENDER_USER
from business.persona import (
    GENDER_LABELS,
    GENDER_OPTIONS,
    PersonaUpdate,
    get_runtime_environment,
)
from core.repositories.file_storage_repository import PLACEHOLDER_NAME
from dashboard.async_utils import run_async

AVATAR_CONTENT_TYPE = "image/png"


def _parse_persona_update(request) -> PersonaUpdate:
    """Convert optional form fields into a PersonaUpdate (None when absent)."""
    return PersonaUpdate(
        name=request.POST.get("name"),
        gender=request.POST.get("gender"),
        profile_picture=request.POST.get("profile_picture"),
        bio=request.POST.get("bio"),
        background_story=request.POST.get("background_story"),
        active_node_limit=parse_limit(request.POST.get("active_node_limit")),
    )


def parse_limit(raw_value):
    """Convert a raw slider value into an int, or None when blank/absent."""
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _parse_conversation_time(raw_value):
    """Parse an HTML datetime-local value into a naive UTC datetime."""
    if raw_value in (None, ""):
        return None

    value = str(raw_value).strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("conversation time must be a valid date and time.") from error

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _message_json(message) -> dict:
    """Return the public JSON representation of a persisted message."""
    return {
        "id": message.id,
        "node_id": message.node_id,
        "sender": message.sender,
        "content": message.content,
        "position": message.position,
        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
    }


def _sender_options(agent):
    """Return the only two valid speaker choices for an agent's timeline."""
    if agent is None:
        return []
    return [
        {"value": MESSAGE_SENDER_USER, "label": "User"},
        {"value": str(agent.id), "label": f"{agent.name} (AI agent)"},
    ]


def _list_personas():
    """Return all personas for the agent switcher."""
    return run_async(container.persona_service().list_personas_async())


def _select_persona(request, personas):
    """Choose the requested agent, falling back to the first available agent."""
    requested_id = request.GET.get("agent_id") or request.POST.get("agent_id")
    if requested_id:
        for persona in personas:
            if str(persona.id) == str(requested_id):
                return persona
    return personas[0] if personas else None


def _request_agent_id(request):
    """Return the explicitly selected agent id from a GET or POST request."""
    return request.POST.get("agent_id") or request.GET.get("agent_id")


def _select_requested_persona(request, personas):
    """Select a requested agent strictly for API writes."""
    requested_id = _request_agent_id(request)
    if requested_id:
        return next(
            (persona for persona in personas if str(persona.id) == str(requested_id)),
            None,
        )
    return personas[0] if personas else None


def _effective_agent_id(request):
    """Return the explicit or currently selected agent for an API mutation."""
    requested_id = _request_agent_id(request)
    if requested_id:
        return requested_id
    selected = _select_persona(request, _list_personas())
    return str(selected.id) if selected is not None else None


def _persona_context(request) -> dict:
    """Build the selected persona, agent switcher, sheets, and runtime context."""
    personas = _list_personas()
    persona = _select_persona(request, personas)
    sheets = []

    if persona is not None:
        sheets = run_async(container.sheet_service().list_sheets_async(persona.id))

    return {
        "persona": persona,
        "agents": personas,
        "selected_agent": persona,
        "sheets": sheets,
        "gender_options": [
            {"value": value, "label": GENDER_LABELS[value]}
            for value in GENDER_OPTIONS
        ],
        "slider_min": 1,
        "slider_max": 200,
        "runtime": get_runtime_environment(container.config()),
    }


def agent_switch(request):
    """Redirect to a dashboard view with the requested agent selected."""
    personas = _list_personas()
    requested_id = request.GET.get("agent_id")
    selected = next(
        (persona for persona in personas if str(persona.id) == str(requested_id)),
        None,
    )
    if selected is None:
        return redirect("dashboard:index")

    destination = (
        reverse("dashboard:event_log")
        if request.GET.get("destination") == "events"
        else reverse("dashboard:index")
    )
    return redirect(f"{destination}?{urlencode({'agent_id': selected.id})}")


def index(request):
    """Render the selected persona dashboard, sheets, and runtime info."""
    return render(request, "dashboard/index.html", _persona_context(request))


def persona_edit(request):
    """Render the persona creation form for a new or first agent."""
    personas = _list_personas()
    persona = _select_persona(request, personas)
    force_new = request.GET.get("new") == "1"

    if persona is None or force_new:
        context = {
            "mode": "create",
            "gender_options": [
                {"value": value, "label": GENDER_LABELS[value]}
                for value in GENDER_OPTIONS
            ],
        }
        return render(request, "dashboard/persona_form.html", context)

    target = reverse("dashboard:index")
    if request.GET.get("agent_id"):
        target = f"{target}?{urlencode({'agent_id': request.GET['agent_id']})}"
    return redirect(target)


def event_log(request):
    """Render one agent's chronological Line of Truth node list and messages."""
    personas = _list_personas()
    persona = _select_persona(request, personas)
    timeline = []

    if persona is not None:
        timeline = run_async(
            container.event_log_manager().list_timeline_async(persona.id)
        )

    return render(
        request,
        "dashboard/event_log.html",
        {
            "persona": persona,
            "selected_agent": persona,
            "agents": personas,
            "sender_options": _sender_options(persona),
            "timeline": timeline,
        },
    )


@require_POST
def event_node_create(request):
    """Persist a new event log node for the selected agent."""
    personas = _list_personas()
    persona = _select_requested_persona(request, personas)
    if persona is None:
        return JsonResponse({"ok": False, "errors": ["Create a persona first."]}, status=404)

    summary = request.POST.get("summary", "").strip()
    try:
        node = run_async(
            container.event_log_manager().add_node_async(
                summary,
                agent_id=persona.id,
            )
        )
    except ValueError as validation_error:
        return JsonResponse(
            {"ok": False, "errors": str(validation_error).split("; ")},
            status=422,
        )

    return JsonResponse(
        {
            "ok": True,
            "node": {
                "id": node.id,
                "sequence_index": node.sequence_index,
                "summary": node.summary,
            },
        }
    )


@require_POST
def event_node_edit(request, node_id: str):
    """Apply an explicit node summary edit through the Layer 2 manager."""
    summary = request.POST.get("summary")

    try:
        node = run_async(
            container.event_log_manager().update_node_async(
                node_id,
                summary=summary,
                agent_id=_effective_agent_id(request),
            )
        )
    except ValueError as validation_error:
        return JsonResponse(
            {"ok": False, "errors": str(validation_error).split("; ")},
            status=422,
        )
    except LookupError as missing:
        return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

    return JsonResponse(
        {
            "ok": True,
            "node": {
                "id": node.id,
                "summary": node.summary,
            },
        }
    )


@require_POST
def event_node_delete(request, node_id: str):
    """Delete an empty timeline node; the manager rejects nodes with messages."""
    try:
        run_async(
            container.event_log_manager().delete_node_async(
                node_id,
                agent_id=_effective_agent_id(request),
            )
        )
    except ValueError as validation_error:
        return JsonResponse(
            {"ok": False, "errors": str(validation_error).split("; ")},
            status=409,
        )
    except LookupError as missing:
        return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

    return JsonResponse({"ok": True, "node_id": node_id})


@require_POST
def event_message_create(request, node_id: str):
    """Add a message to one node with an optional user-supplied conversation time."""
    try:
        timestamp = _parse_conversation_time(
            request.POST.get("conversation_time", request.POST.get("timestamp"))
        )
        message = run_async(
            container.event_log_manager().append_message_async(
                node_id,
                sender=request.POST.get("sender", request.POST.get("said_by", "")),
                content=request.POST.get("content", ""),
                timestamp=timestamp,
                agent_id=_effective_agent_id(request),
            )
        )
    except ValueError as validation_error:
        return JsonResponse(
            {"ok": False, "errors": str(validation_error).split("; ")},
            status=422,
        )
    except LookupError as missing:
        return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

    return JsonResponse({"ok": True, "message": _message_json(message)})


@require_POST
def message_edit(request, message_id: str):
    """Edit a message, including its speaker, text, time, or owning node."""
    values = {}
    if "sender" in request.POST or "said_by" in request.POST:
        values["sender"] = request.POST.get("sender", request.POST.get("said_by", ""))
    if "content" in request.POST:
        values["content"] = request.POST.get("content", "")
    if "conversation_time" in request.POST or "timestamp" in request.POST:
        try:
            timestamp = _parse_conversation_time(
                request.POST.get("conversation_time", request.POST.get("timestamp"))
            )
        except ValueError as validation_error:
            return JsonResponse(
                {"ok": False, "errors": str(validation_error).split("; ")},
                status=422,
            )
        if timestamp is not None:
            values["timestamp"] = timestamp
    if "node_id" in request.POST:
        values["node_id"] = request.POST.get("node_id", "")

    try:
        message = run_async(
            container.event_log_manager().update_message_async(
                message_id,
                agent_id=_effective_agent_id(request),
                **values,
            )
        )
    except ValueError as validation_error:
        return JsonResponse(
            {"ok": False, "errors": str(validation_error).split("; ")},
            status=422,
        )
    except LookupError as missing:
        return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

    return JsonResponse({"ok": True, "message": _message_json(message)})


@require_POST
def message_move(request, message_id: str):
    """Move a message within its node or to another node."""
    try:
        if "node_id" in request.POST:
            message = run_async(
                container.event_log_manager().move_message_async(
                    message_id,
                    request.POST.get("node_id", ""),
                    agent_id=_effective_agent_id(request),
                )
            )
        else:
            message = run_async(
                container.event_log_manager().move_message_position_async(
                    message_id,
                    request.POST.get("direction", ""),
                    agent_id=_effective_agent_id(request),
                )
            )
    except ValueError as validation_error:
        return JsonResponse(
            {"ok": False, "errors": str(validation_error).split("; ")},
            status=422,
        )
    except LookupError as missing:
        return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

    return JsonResponse({"ok": True, "message": _message_json(message)})


@require_POST
def message_delete(request, message_id: str):
    """Delete a message so its owning node can become empty and be removed."""
    try:
        message = run_async(
            container.event_log_manager().delete_message_async(
                message_id,
                agent_id=_effective_agent_id(request),
            )
        )
    except LookupError as missing:
        return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

    return JsonResponse({"ok": True, "message_id": message.id})


@require_POST
def persona_create(request):
    """Validate and persist a new persona through the Layer 2 service."""
    update = _parse_persona_update(request)

    # Empty optional fields fall back to the service's creation defaults.
    update.gender = update.gender or None
    update.profile_picture = update.profile_picture or None
    update.bio = update.bio or None
    update.background_story = update.background_story or None

    try:
        created = run_async(container.persona_service().create_persona(update))
    except ValueError as validation_error:
        context = {
            "mode": "create",
            "errors": str(validation_error).split("; "),
            "form": request.POST,
            "gender_options": [
                {"value": value, "label": GENDER_LABELS[value]}
                for value in GENDER_OPTIONS
            ],
        }
        return render(request, "dashboard/persona_form.html", context, status=422)

    return redirect(
        f"{reverse('dashboard:index')}?{urlencode({'agent_id': created.id})}"
    )


@require_POST
def persona_update(request):
    """Validate and persist persona changes through the Layer 2 service (jQuery/AJAX)."""
    update = _parse_persona_update(request)

    agent_id = request.POST.get("agent_id")
    if not agent_id:
        return JsonResponse({"ok": False, "errors": ["agent_id is required."]}, status=400)

    try:
        persona = run_async(
            container.persona_service().update_persona(agent_id, update)
        )
    except ValueError as validation_error:
        return JsonResponse(
            {"ok": False, "errors": str(validation_error).split("; ")},
            status=422,
        )
    except LookupError as missing:
        return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

    return JsonResponse(
        {
            "ok": True,
            "persona": {
                "id": persona.id,
                "name": persona.name,
                "gender": persona.gender,
                "bio": persona.bio,
                "background_story": persona.background_story,
                "active_node_limit": persona.active_node_limit,
            },
        }
    )
@require_POST
def sheet_upload(request):
    """Store an uploaded character reference sheet for the selected agent."""
    persona = _select_persona(request, _list_personas())
    if persona is None:
        return JsonResponse({"ok": False, "errors": ["Create a persona first."]}, status=404)

    uploaded = request.FILES.get("sheet")
    if uploaded is None:
        return JsonResponse({"ok": False, "errors": ["Choose an image file to upload."]}, status=400)

    data = uploaded.read()
    try:
        sheet = run_async(
            container.sheet_service().upload_sheet_async(
                persona.id,
                uploaded.name,
                uploaded.content_type or "",
                data,
            )
        )
    except ValueError as validation_error:
        return JsonResponse({"ok": False, "errors": [str(validation_error)]}, status=422)

    return JsonResponse(
        {
            "ok": True,
            "sheet": {
                "id": sheet.id,
                "original_filename": sheet.original_filename,
            },
        }
    )
@require_POST
def sheet_delete(request, sheet_id: str):
    """Remove a character reference sheet and its stored file."""
    try:
        run_async(container.sheet_service().delete_sheet_async(sheet_id))
    except LookupError:
        return JsonResponse({"ok": False, "errors": ["Sheet not found."]}, status=404)

    return JsonResponse({"ok": True})


@require_POST
def avatar_generate(request):
    """Kick off profile picture generation for the selected agent."""
    persona = _select_persona(request, _list_personas())
    if persona is None:
        return JsonResponse({"ok": False, "errors": ["Create a persona first."]}, status=404)

    try:
        stored_filename = run_async(
            container.sheet_service().generate_avatar_async(persona.id)
        )
    except NotImplementedError:
        return JsonResponse(
            {
                "ok": False,
                "errors": [
                    "Profile picture generation is not available in this phase. "
                    "The provider hook is ready for a plug-in implementation."
                ],
            },
            status=501,
        )
    except LookupError as missing:
        return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

    run_async(
        container.persona_service().update_persona(
            persona.id,
            PersonaUpdate(profile_picture=stored_filename),
        )
    )
    return JsonResponse({"ok": True, "profile_picture": stored_filename})
def sheet_image(request, sheet_id: str):
    """Serve the stored bytes of a reference sheet image."""
    data = run_async(container.sheet_service().open_sheet_async(sheet_id))

    if data is None:
        return JsonResponse({"ok": False, "errors": ["Sheet not found."]}, status=404)

    return HttpResponse(data, content_type="image/png")


def avatar(request):
    """Serve the selected persona's profile picture or placeholder."""
    persona = _select_persona(request, _list_personas())
    profile_picture = (persona.profile_picture or "").strip() if persona else ""

    if profile_picture.startswith("generated:"):
        return JsonResponse(
            {"ok": False, "errors": ["Profile picture has not been generated yet."]},
            status=501,
        )

    if profile_picture.startswith(("http://", "https://")):
        return redirect(profile_picture)

    storage = container.storage()
    data = None
    if profile_picture:
        try:
            data = storage.open(profile_picture)
        except ValueError:
            # Free-form path/URL values are not storage filenames.
            data = None

    if data is None:
        data = storage.open(PLACEHOLDER_NAME)

    return HttpResponse(data, content_type=AVATAR_CONTENT_TYPE)
