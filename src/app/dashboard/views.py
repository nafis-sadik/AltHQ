"""Thin Django views for the persona dashboard; all logic delegates to Layer 2."""

from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from agent_dashboard.container import container
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


def _persona_context() -> dict:
    """Build the shared dashboard context: persona, sheets, and runtime values."""
    persona = run_async(container.persona_service().get_persona())
    sheets = []

    if persona is not None:
        sheets = run_async(container.sheet_service().list_sheets_async(persona.id))

    return {
        "persona": persona,
        "sheets": sheets,
        "gender_options": [
            {"value": value, "label": GENDER_LABELS[value]}
            for value in GENDER_OPTIONS
        ],
        "slider_min": 1,
        "slider_max": 200,
        "runtime": get_runtime_environment(container.config()),
    }
def index(request):
    """Render the dashboard: persona state, sheets, and runtime info."""
    return render(request, "dashboard/index.html", _persona_context())


def persona_edit(request):
    """Render the persona creation form when no persona exists yet."""
    persona = run_async(container.persona_service().get_persona())

    if persona is None:
        context = {
            "mode": "create",
            "gender_options": [
                {"value": value, "label": GENDER_LABELS[value]}
                for value in GENDER_OPTIONS
            ],
        }
        return render(request, "dashboard/persona_form.html", context)

    return redirect("dashboard:index")


def event_log(request):
    """Render the long-term memory timeline via the Layer 2 event log manager."""
    persona = run_async(container.persona_service().get_persona())
    timeline = []
    memory_window = None

    if persona is not None:
        timeline = run_async(
            container.event_log_manager().list_timeline_async(persona.id)
        )
        memory_window = run_async(
            container.event_log_manager().get_memory_window_async(persona.id)
        )

    return render(
        request,
        "dashboard/event_log.html",
        {
            "persona": persona,
            "timeline": timeline,
            "memory_window": memory_window,
            "active_node_limit": (
                persona.active_node_limit if persona is not None else None
            ),
        },
    )


@require_POST
def event_node_create(request):
    """Persist a new event log node through the Layer 2 event log manager."""
    persona = run_async(container.persona_service().get_persona())
    if persona is None:
        return JsonResponse({"ok": False, "errors": ["Create a persona first."]}, status=404)

    summary = request.POST.get("summary", "").strip()
    try:
        node = run_async(
            container.event_log_manager().append_node_async(
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
    """Apply a silent God-Mode edit to a past event node via the Layer 2 manager.

    The update bypasses audit rows and forces prompt-cache invalidation, so the
    next execution cycle recompiles the active memory window.
    """
    summary = request.POST.get("summary")
    is_active_raw = request.POST.get("is_active")

    is_active = None
    if is_active_raw is not None and is_active_raw != "":
        is_active = is_active_raw.strip().lower() in ("1", "true", "yes", "on")

    try:
        node = run_async(
            container.event_log_manager().silent_edit_node_async(
                node_id,
                summary=summary,
                is_active=is_active,
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
                "is_active": node.is_active,
            },
        }
    )


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
        run_async(container.persona_service().create_persona(update))
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

    return redirect("dashboard:index")
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
    """Store an uploaded character reference sheet for the agent."""
    persona = run_async(container.persona_service().get_persona())
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
    """Kick off profile picture generation via the plug-n-play provider hook."""
    persona = run_async(container.persona_service().get_persona())
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
    """Serve the persona's profile picture, a placeholder, or 501 when not generated."""
    persona = run_async(container.persona_service().get_persona())
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
