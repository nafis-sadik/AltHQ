"""Layer 1 controller for the Line of Truth (event log) domain.

Owns the SSR timeline page and the node/message REST API (POST create, PUT
edit/move, DELETE). All timeline business logic is delegated to the injected
``IEventLogService``; persona selection uses the injected ``IPersonaService``.
Contains zero business rules.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render

from business.memory import IEventLogService, MESSAGE_SENDER_USER
from business.persona import IPersonaService
from dashboard.async_utils import run_async
from dashboard.controllers.params import request_params
from dashboard.controllers.persona_controller import (
    effective_agent_id,
    list_personas,
    select_persona,
    select_requested_persona,
)


def parse_conversation_time(raw_value) -> Optional[datetime]:
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


def message_json(message: Any) -> dict:
    """Return the public JSON representation of a persisted message."""
    return {
        "id": message.id,
        "node_id": message.node_id,
        "sender": message.sender,
        "content": message.content,
        "position": message.position,
        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
    }


class EventLogController:
    """HTTP entry point for one agent's chronological Line of Truth timeline."""

    def __init__(
        self,
        persona_service: IPersonaService,
        event_log_service: IEventLogService,
    ) -> None:
        """Store the injected persona and timeline domain services."""
        self._personas = persona_service
        self._events = event_log_service

    # -- SSR page (HttpGet) --------------------------------------------------

    def get_event_log(self, request: HttpRequest):
        """Render one agent's chronological Line of Truth node list and messages."""
        personas = list_personas(self._personas)
        persona = select_persona(self._personas, request, personas)
        timeline = []

        if persona is not None:
            timeline = run_async(self._events.list_timeline_async(persona.id))

        return render(
            request,
            "dashboard/event_log.html",
            {
                "persona": persona,
                "selected_agent": persona,
                "agents": personas,
                "active_agent": run_async(self._personas.get_active_async()),
                "sender_options": self._sender_options(persona),
                "timeline": timeline,
            },
        )

    # -- Nodes (HttpPost/HttpPut/HttpDelete) ---------------------------------

    def post_create_node(self, request: HttpRequest):
        """Persist a new event log node for the selected agent."""
        personas = list_personas(self._personas)
        persona = select_requested_persona(self._personas, request, personas)
        if persona is None:
            return JsonResponse({"ok": False, "errors": ["Create a persona first."]}, status=404)

        summary = request.POST.get("summary", "").strip()
        try:
            node = run_async(
                self._events.add_node_async(
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

    def put_update_node(self, request: HttpRequest, node_id: str):
        """Apply an explicit node summary edit through the Layer 2 service."""
        summary = request_params(request).get("summary")

        try:
            node = run_async(
                self._events.update_node_async(
                    node_id,
                    summary=summary,
                    agent_id=effective_agent_id(self._personas, request),
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

    def delete_node(self, request: HttpRequest, node_id: str):
        """Delete an empty timeline node; the service rejects nodes with messages."""
        try:
            run_async(
                self._events.delete_node_async(
                    node_id,
                    agent_id=effective_agent_id(self._personas, request),
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

    # -- Messages (HttpPost/HttpPut/HttpDelete) ------------------------------

    def post_create_message(self, request: HttpRequest, node_id: str):
        """Add a message to one node with an optional user-supplied conversation time."""
        params = request_params(request)
        try:
            timestamp = parse_conversation_time(
                params.get("conversation_time", params.get("timestamp"))
            )
            message = run_async(
                self._events.append_message_async(
                    node_id,
                    sender=params.get("sender", params.get("said_by", "")),
                    content=params.get("content", ""),
                    timestamp=timestamp,
                    agent_id=effective_agent_id(self._personas, request),
                )
            )
        except ValueError as validation_error:
            return JsonResponse(
                {"ok": False, "errors": str(validation_error).split("; ")},
                status=422,
            )
        except LookupError as missing:
            return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

        return JsonResponse({"ok": True, "message": message_json(message)})

    def put_update_message(self, request: HttpRequest, message_id: str):
        """Edit a message, including its speaker, text, time, or owning node."""
        params = request_params(request)
        values = {}
        if "sender" in params or "said_by" in params:
            values["sender"] = params.get("sender", params.get("said_by", ""))
        if "content" in params:
            values["content"] = params.get("content", "")
        if "conversation_time" in params or "timestamp" in params:
            try:
                timestamp = parse_conversation_time(
                    params.get("conversation_time", params.get("timestamp"))
                )
            except ValueError as validation_error:
                return JsonResponse(
                    {"ok": False, "errors": str(validation_error).split("; ")},
                    status=422,
                )
            if timestamp is not None:
                values["timestamp"] = timestamp
        if "node_id" in params:
            values["node_id"] = params.get("node_id", "")

        try:
            message = run_async(
                self._events.update_message_async(
                    message_id,
                    agent_id=effective_agent_id(self._personas, request),
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

        return JsonResponse({"ok": True, "message": message_json(message)})

    def put_move_message(self, request: HttpRequest, message_id: str):
        """Move a message within its node or to another node."""
        params = request_params(request)
        try:
            if "node_id" in params:
                message = run_async(
                    self._events.move_message_async(
                        message_id,
                        params.get("node_id", ""),
                        agent_id=effective_agent_id(self._personas, request),
                    )
                )
            else:
                message = run_async(
                    self._events.move_message_position_async(
                        message_id,
                        params.get("direction", ""),
                        agent_id=effective_agent_id(self._personas, request),
                    )
                )
        except ValueError as validation_error:
            return JsonResponse(
                {"ok": False, "errors": str(validation_error).split("; ")},
                status=422,
            )
        except LookupError as missing:
            return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

        return JsonResponse({"ok": True, "message": message_json(message)})

    def delete_message(self, request: HttpRequest, message_id: str):
        """Delete a message so its owning node can become empty and be removed."""
        try:
            message = run_async(
                self._events.delete_message_async(
                    message_id,
                    agent_id=effective_agent_id(self._personas, request),
                )
            )
        except LookupError as missing:
            return JsonResponse({"ok": False, "errors": [str(missing)]}, status=404)

        return JsonResponse({"ok": True, "message_id": message.id})

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _sender_options(agent) -> List[dict]:
        """Return the only two valid speaker choices for an agent's timeline."""
        if agent is None:
            return []
        return [
            {"value": MESSAGE_SENDER_USER, "label": "User"},
            {"value": str(agent.id), "label": f"{agent.name} (AI agent)"},
        ]