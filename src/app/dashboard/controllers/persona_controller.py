"""Layer 1 controller for the entire persona domain.

Owns the SSR dashboard pages, the persona REST API (POST create / PUT update /
GET list + detail), avatar serving, and character reference sheets. All business
logic is delegated to the injected ``IPersonaService`` and sheet service; this
class contains zero business rules.
"""

from typing import Any, List, Optional
from urllib.parse import urlencode

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from business.persona import (
    IPersonaService,
    PersonaUpdate,
    get_runtime_environment,
)
from core.dtos.db_entities import Gender
from core.repositories.file_storage_repository import PLACEHOLDER_NAME
from dashboard.async_utils import run_async
from dashboard.controllers.params import request_params

AVATAR_CONTENT_TYPE = "image/png"

# Human-readable labels for the canonical Gender enum values.
GENDER_LABELS = {
    Gender.MALE: "Male",
    Gender.FEMALE: "Female",
    Gender.NON_BINARY: "Non-binary",
    Gender.PREFER_NOT_TO_SAY: "Prefer not to say",
}


# ---------------------------------------------------------------------------
# Shared persona-selection helpers (also used by the event log controller)
# ---------------------------------------------------------------------------


def list_personas(service: IPersonaService) -> List[Any]:
    """Return all personas (name-ordered) for the agent switcher."""
    page = run_async(service.GetPagedPersona(1, page_size=1000))
    return list(page.source_data or [])


def select_persona(
    service: IPersonaService,
    request: HttpRequest,
    personas: List[Any],
) -> Optional[Any]:
    """Choose the requested agent, falling back to the first available agent."""
    params = request_params(request)
    requested_id = request.GET.get("agent_id") or params.get("agent_id")
    if requested_id:
        for persona in personas:
            if str(persona.id) == str(requested_id):
                return persona
    return personas[0] if personas else None


def request_agent_id(request: HttpRequest) -> Optional[str]:
    """Return the explicitly selected agent id from a GET or form body request."""
    return request_params(request).get("agent_id") or request.GET.get("agent_id")


def select_requested_persona(
    service: IPersonaService,
    request: HttpRequest,
    personas: List[Any],
) -> Optional[Any]:
    """Select a requested agent strictly for API writes."""
    requested_id = request_agent_id(request)
    if requested_id:
        return next(
            (persona for persona in personas if str(persona.id) == str(requested_id)),
            None,
        )
    return personas[0] if personas else None


def effective_agent_id(
    service: IPersonaService,
    request: HttpRequest,
) -> Optional[str]:
    """Return the explicit or currently selected agent for an API mutation."""
    requested_id = request_agent_id(request)
    if requested_id:
        return requested_id
    selected = select_persona(service, request, list_personas(service))
    return str(selected.id) if selected is not None else None


def parse_limit(raw_value):
    """Convert a raw slider value into an int, or None when blank/absent."""
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def persona_json(persona: Any) -> dict:
    """Return the public JSON representation of a persona row."""
    return {
        "id": persona.id,
        "name": persona.name,
        "gender": persona.gender,
        "profile_picture": persona.profile_picture,
        "bio": persona.bio,
        "background_story": persona.background_story,
        "active_node_limit": persona.active_node_limit,
    }


def _gender_options() -> List[dict]:
    """Return the canonical gender dropdown options shared by the SSR pages."""
    return [
        {"value": gender.value, "label": GENDER_LABELS[gender]}
        for gender in Gender
    ]


class PersonaController:
    """HTTP entry point for the persona domain.

    The class is constructed once by the IoC container and receives its
    :class:`IPersonaService` (plus the sheet/storage/config collaborators)
    through dependency injection.
    """

    def __init__(
        self,
        persona_service: IPersonaService,
        sheet_service: Any,
        config: Any,
        storage: Any,
    ) -> None:
        """Store the injected persona service and persona-domain collaborators."""
        self._personas = persona_service
        self._sheets = sheet_service
        self._config = config
        self._storage = storage

    # -- SSR pages (HttpGet) -------------------------------------------------

    def get_dashboard(self, request: HttpRequest):
        """Render the selected persona dashboard, sheets, and runtime info."""
        return render(request, "dashboard/index.html", self._persona_context(request))

    def get_new_persona(self, request: HttpRequest):
        """Render the persona creation form for a new or first agent."""
        personas = list_personas(self._personas)
        persona = select_persona(self._personas, request, personas)
        force_new = request.GET.get("new") == "1"

        if persona is None or force_new:
            return render(
                request,
                "dashboard/persona_form.html",
                {
                    "mode": "create",
                    "gender_options": _gender_options(),
                },
            )

        target = reverse("dashboard:index")
        if request.GET.get("agent_id"):
            target = f"{target}?{urlencode({'agent_id': request.GET['agent_id']})}"
        return redirect(target)

    def get_agent_switch(self, request: HttpRequest):
        """Redirect to a dashboard view with the requested agent selected."""
        personas = list_personas(self._personas)
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

    # -- Persona REST API (HttpGet/HttpPost/HttpPut) -------------------------

    def get_personas(self, request: HttpRequest):
        """Return a paged JSON list of personas (order: name)."""
        page = parse_limit(request.GET.get("page")) or 1
        page_size = parse_limit(request.GET.get("page_size")) or 20
        page_result = run_async(self._personas.GetPagedPersona(page, page_size))
        total_pages = (
            (page_result.total_items + page_result.page_length - 1)
            // page_result.page_length
            if page_result.page_length
            else 0
        )
        return JsonResponse(
            {
                "ok": True,
                "items": [persona_json(persona) for persona in (page_result.source_data or [])],
                "total": page_result.total_items,
                "page": page_result.page_number,
                "page_size": page_result.page_length,
                "total_pages": total_pages,
            }
        )

    def post_create(self, request: HttpRequest):
        """Validate and persist a new persona through the Layer 2 service."""
        update = self._parse_persona_update(request)

        # Empty optional fields fall back to the service's creation defaults.
        update.gender = update.gender or None
        update.profile_picture = update.profile_picture or None
        update.bio = update.bio or None
        update.background_story = update.background_story or None

        try:
            created = run_async(self._personas.AddNewAsync(update))
        except ValueError as validation_error:
            return JsonResponse(
                {"ok": False, "errors": str(validation_error).split("; ")},
                status=422,
            )

        return JsonResponse(
            {
                "ok": True,
                "persona": persona_json(created),
                "redirect": (
                    f"{reverse('dashboard:index')}"
                    f"?{urlencode({'agent_id': created.id})}"
                ),
            },
            status=201,
        )

    def get_persona(self, request: HttpRequest, agent_id: str):
        """Return a single persona's JSON state by id."""
        persona = run_async(self._personas.GetByIdAsync(agent_id))
        if persona is None:
            return JsonResponse({"ok": False, "errors": ["Persona not found."]}, status=404)
        return JsonResponse({"ok": True, "persona": persona_json(persona)})

    def put_update(self, request: HttpRequest, agent_id: str):
        """Validate and persist persona changes through the Layer 2 service."""
        update = self._parse_persona_update(request)

        try:
            persona = run_async(
                self._personas.UpdateExistingAsync(agent_id, update)
            )
        except ValueError as validation_error:
            return JsonResponse(
                {"ok": False, "errors": str(validation_error).split("; ")},
                status=422,
            )
        except LookupError as missing:
            return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

        return JsonResponse({"ok": True, "persona": persona_json(persona)})

    # -- Avatar (HttpGet/HttpPost) -------------------------------------------

    def get_avatar(self, request: HttpRequest):
        """Serve the selected persona's profile picture or placeholder."""
        persona = select_persona(self._personas, request, list_personas(self._personas))
        profile_picture = (persona.profile_picture or "").strip() if persona else ""

        if profile_picture.startswith("generated:"):
            return JsonResponse(
                {"ok": False, "errors": ["Profile picture has not been generated yet."]},
                status=501,
            )

        if profile_picture.startswith(("http://", "https://")):
            return redirect(profile_picture)

        data = None
        if profile_picture:
            try:
                data = self._storage.open(profile_picture)
            except ValueError:
                # Free-form path/URL values are not storage filenames.
                data = None

        if data is None:
            data = self._storage.open(PLACEHOLDER_NAME)

        return HttpResponse(data, content_type=AVATAR_CONTENT_TYPE)

    def post_generate_avatar(self, request: HttpRequest):
        """Kick off profile picture generation for the selected agent."""
        persona = select_persona(self._personas, request, list_personas(self._personas))
        if persona is None:
            return JsonResponse({"ok": False, "errors": ["Create a persona first."]}, status=404)

        try:
            stored_filename = run_async(
                self._sheets.generate_avatar_async(persona.id)
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
            self._personas.UpdateExistingAsync(
                persona.id,
                PersonaUpdate(profile_picture=stored_filename),
            )
        )
        return JsonResponse({"ok": True, "profile_picture": stored_filename})

    # -- Character sheets (HttpPost/HttpDelete/HttpGet) ----------------------

    def post_upload_sheet(self, request: HttpRequest):
        """Store an uploaded character reference sheet for the selected agent."""
        persona = select_persona(self._personas, request, list_personas(self._personas))
        if persona is None:
            return JsonResponse({"ok": False, "errors": ["Create a persona first."]}, status=404)

        uploaded = request.FILES.get("sheet")
        if uploaded is None:
            return JsonResponse(
                {"ok": False, "errors": ["Choose an image file to upload."]},
                status=400,
            )

        data = uploaded.read()
        try:
            sheet = run_async(
                self._sheets.upload_sheet_async(
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

    def delete_sheet(self, request: HttpRequest, sheet_id: str):
        """Remove a character reference sheet and its stored file."""
        try:
            run_async(self._sheets.delete_sheet_async(sheet_id))
        except LookupError:
            return JsonResponse({"ok": False, "errors": ["Sheet not found."]}, status=404)

        return JsonResponse({"ok": True})

    def get_sheet_image(self, request: HttpRequest, sheet_id: str):
        """Serve the stored bytes of a reference sheet image."""
        data = run_async(self._sheets.open_sheet_async(sheet_id))

        if data is None:
            return JsonResponse({"ok": False, "errors": ["Sheet not found."]}, status=404)

        return HttpResponse(data, content_type="image/png")

    # -- Helpers -------------------------------------------------------------

    def _persona_context(self, request: HttpRequest) -> dict:
        """Build the selected persona, agent switcher, sheets, and runtime context."""
        personas = list_personas(self._personas)
        persona = select_persona(self._personas, request, personas)
        sheets = []

        if persona is not None:
            sheets = run_async(self._sheets.list_sheets_async(persona.id))

        return {
            "persona": persona,
            "agents": personas,
            "selected_agent": persona,
            "sheets": sheets,
            "gender_options": _gender_options(),
            "slider_min": 1,
            "slider_max": 200,
            "runtime": get_runtime_environment(self._config),
        }

    def _parse_persona_update(self, request: HttpRequest) -> PersonaUpdate:
        """Convert optional form fields into a PersonaUpdate (None when absent)."""
        params = request_params(request)
        return PersonaUpdate(
            name=params.get("name"),
            gender=params.get("gender"),
            profile_picture=params.get("profile_picture"),
            bio=params.get("bio"),
            background_story=params.get("background_story"),
            active_node_limit=parse_limit(params.get("active_node_limit")),
        )