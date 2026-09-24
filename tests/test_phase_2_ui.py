"""Layer 1 UI and API tests for the explicit multi-agent Line of Truth workflow."""

import re
from urllib.parse import urlencode

# Paths, settings, and artifact isolation are configured in conftest.py.


def _put(client, url, data):
    """Send a PUT with a jQuery-serialized (urlencoded) form body."""
    return client.put(
        url,
        urlencode(data),
        content_type="application/x-www-form-urlencoded",
    )


def _create_persona(client):
    """Create the default persona used by the event log flows."""
    return client.post(
        "/api/personas/",
        {"name": "Aria", "gender": "female", "bio": "A warm companion."},
    )


def _agent_id(client):
    """Read the active agent id from the rendered persona dashboard."""
    html = client.get("/").content.decode()
    return html.split('name="agent_id" value="')[1].split('"')[0]


def _create_node(client, summary):
    """Create one timeline node and return its API payload."""
    response = client.post("/api/events/", {"summary": summary})
    assert response.status_code == 200
    return response.json()["node"]


def test_event_log_page_without_persona_shows_empty_state(client):
    """Without a persona the event log must guide the user to create one first."""
    response = client.get("/events/")
    html = response.content.decode()

    assert response.status_code == 200
    assert "Line of Truth" in html
    assert "Create a persona before recording timeline nodes and messages." in html


def test_event_log_empty_timeline_when_no_nodes(client):
    """With a persona but no nodes the timeline must show its empty state."""
    _create_persona(client)

    response = client.get("/events/")
    html = response.content.decode()

    assert response.status_code == 200
    assert "No nodes recorded yet." in html
    assert "Add timeline node" in html
    assert "plain chronological node list" in html


def test_event_node_create_and_timeline_render(client):
    """Adding a node must persist it and render an explicit message editor."""
    _create_persona(client)
    created = _create_node(client, "Woke up at dawn.")
    assert created["sequence_index"] == 1

    html = client.get("/events/").content.decode()
    assert "Woke up at dawn." in html
    assert "Node #1" in html
    assert "Add message" in html
    assert "Delete" in html
    assert "God-Mode" not in html


def test_event_node_create_rejects_blank_summary(client):
    """Blank node summaries must be rejected without a server error."""
    _create_persona(client)

    response = client.post("/api/events/", {"summary": "   "})
    assert response.status_code == 422
    assert "summary must not be blank." in response.json()["errors"]


def test_event_log_page_links_back_to_persona_dashboard(client):
    """The event log navbar must include the persona dashboard link."""
    html = client.get("/events/").content.decode()
    assert 'href="/"' in html


def test_explicit_node_edit_is_visible_and_not_silent(client):
    """Node edits are ordinary visible timeline operations."""
    _create_persona(client)
    node = _create_node(client, "Original memory.")

    edited = _put(
        client,
        f"/api/events/{node['id']}/",
        {"summary": "The corrected memory."},
    )
    assert edited.status_code == 200
    assert edited.json()["node"]["summary"] == "The corrected memory."

    html = client.get("/events/").content.decode()
    assert "The corrected memory." in html
    assert "Original memory." not in html
    assert "never hidden" in html
    assert "God-Mode" not in html


def test_node_delete_requires_zero_messages(client):
    """A node with messages must stay until its messages are moved or deleted."""
    _create_persona(client)
    source = _create_node(client, "Source node.")
    target = _create_node(client, "Target node.")
    message = client.post(
        f"/api/events/{source['id']}/messages/",
        {"sender": "user", "content": "Move me."},
    ).json()["message"]

    blocked = client.delete(f"/api/events/{source['id']}/")
    assert blocked.status_code == 409
    assert "messages" in blocked.json()["errors"][0].lower()

    moved = _put(
        client,
        f"/api/messages/{message['id']}/move/",
        {"node_id": target["id"]},
    )
    assert moved.status_code == 200
    assert moved.json()["message"]["node_id"] == target["id"]

    deleted = client.delete(f"/api/events/{source['id']}/")
    assert deleted.status_code == 200
    html = client.get("/events/").content.decode()
    assert "Source node." not in html
    assert "Target node." in html


def test_message_create_and_edit_support_speaker_and_manual_time(client):
    """Message forms persist a speaker, content, and user-selected conversation time."""
    _create_persona(client)
    agent_id = _agent_id(client)
    node = _create_node(client, "A conversation happened.")

    created = client.post(
        f"/api/events/{node['id']}/messages/",
        {
            "agent_id": agent_id,
            "sender": "user",
            "content": "What happened?",
            "conversation_time": "2024-05-04T10:30",
        },
    )
    assert created.status_code == 200
    message = created.json()["message"]
    assert message["sender"] == "user"
    assert message["content"] == "What happened?"
    assert message["position"] == 0
    assert message["timestamp"].startswith("2024-05-04T10:30")

    edited = _put(
        client,
        f"/api/messages/{message['id']}/",
        {
            "agent_id": agent_id,
            "sender": agent_id,
            "content": "I remembered the garden.",
            "conversation_time": "2024-05-04T10:35",
        },
    )
    assert edited.status_code == 200
    updated = edited.json()["message"]
    assert updated["sender"] == agent_id
    assert updated["content"] == "I remembered the garden."
    assert updated["timestamp"].startswith("2024-05-04T10:35")

    html = client.get("/events/").content.decode()
    assert "I remembered the garden." in html
    assert "Conversation time" in html
    assert "Move to node" in html
    assert "God-Mode" not in html


def test_messages_can_reorder_and_be_deleted(client):
    """Message position controls up/down order and deletion is explicit."""
    _create_persona(client)
    agent_id = _agent_id(client)
    node = _create_node(client, "A conversation happened.")
    first = client.post(
        f"/api/events/{node['id']}/messages/",
        {"agent_id": agent_id, "sender": "user", "content": "One"},
    ).json()["message"]
    second = client.post(
        f"/api/events/{node['id']}/messages/",
        {"agent_id": agent_id, "sender": agent_id, "content": "Two"},
    ).json()["message"]
    third = client.post(
        f"/api/events/{node['id']}/messages/",
        {"agent_id": agent_id, "sender": "user", "content": "Three"},
    ).json()["message"]

    moved = _put(
        client,
        f"/api/messages/{third['id']}/move/",
        {"direction": "up"},
    )
    assert moved.status_code == 200
    html = client.get("/events/").content.decode()
    assert html.index("Three") < html.index("Two")

    invalid = _put(
        client,
        f"/api/messages/{second['id']}/move/",
        {"direction": "sideways"},
    )
    assert invalid.status_code == 422

    deleted = client.delete(f"/api/messages/{second['id']}/")
    assert deleted.status_code == 200
    html = client.get("/events/").content.decode()
    assert "Two" not in html


def test_agents_have_isolated_timelines_and_switcher(client):
    """Each agent gets its own Line of Truth and selectable speaker identity."""
    _create_persona(client)
    first_agent_id = _agent_id(client)
    second = client.post(
        "/api/personas/",
        {"name": "Beacon", "gender": "non_binary", "bio": "Second agent."},
    )
    assert second.status_code == 201

    dashboard = client.get("/").content.decode()
    agent_ids = re.findall(r'<option value="([a-f0-9]+)"', dashboard)
    assert len(agent_ids) >= 2
    second_agent_id = next(agent_id for agent_id in agent_ids if agent_id != first_agent_id)

    first_node = _create_node(client, "Aria node.")
    second_node_response = client.post(
        "/api/events/",
        {"agent_id": second_agent_id, "summary": "Beacon node."},
    )
    assert second_node_response.status_code == 200
    second_node = second_node_response.json()["node"]

    invalid_sender = client.post(
        f"/api/events/{second_node['id']}/messages/",
        {"agent_id": second_agent_id, "sender": "someone-else", "content": "No."},
    )
    assert invalid_sender.status_code == 422

    message = client.post(
        f"/api/events/{second_node['id']}/messages/",
        {
            "agent_id": second_agent_id,
            "sender": second_agent_id,
            "content": "I am Beacon.",
        },
    )
    assert message.status_code == 200

    switched = client.get(
        f"/agents/switch/?agent_id={second_agent_id}&destination=events"
    )
    assert switched.status_code == 302
    assert f"agent_id={second_agent_id}" in switched["Location"]

    html = client.get(f"/events/?agent_id={second_agent_id}").content.decode()
    assert "Beacon node." in html
    assert "Aria node." not in html
    assert "Beacon (AI agent)" in html
    assert f'value="{second_agent_id}"' in html
    assert first_node["id"] not in html
