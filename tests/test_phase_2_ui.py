"""Layer 1 UI tests: the event log timeline vertical slice for Phase 2 Task 1."""

# Paths, settings, and artifact isolation are configured in conftest.py.


def test_event_log_page_without_persona_shows_empty_state(client):
    """Without a persona the event log must guide the user to create one first."""
    response = client.get("/events/")
    html = response.content.decode()

    assert response.status_code == 200
    assert "Line of Truth" in html
    assert "Create a persona before recording event memories." in html


def test_event_log_empty_timeline_when_no_nodes(client):
    """With a persona but no events the timeline must show its empty state."""
    client.post(
        "/persona/create/",
        {"name": "Aria", "gender": "female", "bio": "A warm companion."},
    )

    response = client.get("/events/")
    html = response.content.decode()

    assert response.status_code == 200
    assert "No events recorded yet." in html
    assert "Active node limit:" in html
    assert "Append memory" in html


def test_event_node_create_and_timeline_render(client):
    """Appending an event must persist it and render it on the timeline."""
    client.post(
        "/persona/create/",
        {"name": "Aria", "gender": "female", "bio": "A warm companion."},
    )

    created = client.post("/api/events/create/", {"summary": "Woke up at dawn."})
    assert created.status_code == 200
    payload = created.json()
    assert payload["ok"] is True
    assert payload["node"]["sequence_index"] == 1

    dashboard = client.get("/events/").content.decode()
    assert "Woke up at dawn." in dashboard
    assert "#1" in dashboard
    assert "active" in dashboard


def test_event_node_create_rejects_blank_summary(client):
    """Blank summaries must be rejected without a server error."""
    client.post(
        "/persona/create/",
        {"name": "Aria", "gender": "female", "bio": "A warm companion."},
    )

    response = client.post("/api/events/create/", {"summary": "   "})
    assert response.status_code == 422
    assert "summary must not be blank." in response.json()["errors"]


def test_event_log_page_links_back_to_persona_dashboard(client):
    """The event log navbar must include the persona dashboard link."""
    html = client.get("/events/").content.decode()
    assert 'href="/"' in html


def _create_persona(client):
    """Create the default persona used by the event log flows."""
    client.post(
        "/persona/create/",
        {"name": "Aria", "gender": "female", "bio": "A warm companion."},
    )


def test_memory_window_panel_renders_sliding_window_stats(client):
    """The timeline must surface the active window, archived, and limit counts."""
    _create_persona(client)
    for index in range(1, 6):
        client.post("/api/events/create/", {"summary": f"Memory {index}."})

    html = client.get("/events/").content.decode()
    assert "Active memory window" in html
    assert "Sliding Window · MemoryWindowService" in html
    assert "window limit" in html
    assert "God-Mode" in html


def test_god_mode_silent_edit_rewrites_node(client):
    """The silent edit endpoint must rewrite a past node without audit output."""
    _create_persona(client)
    created = client.post("/api/events/create/", {"summary": "Original memory."})
    node_id = created.json()["node"]["id"]

    edited = client.post(
        f"/api/events/{node_id}/edit/",
        {"summary": "The accepted reality.", "is_active": "0"},
    )
    assert edited.status_code == 200
    payload = edited.json()
    assert payload["ok"] is True
    assert payload["node"]["summary"] == "The accepted reality."
    assert payload["node"]["is_active"] is False

    html = client.get("/events/").content.decode()
    assert "The accepted reality." in html
    assert "Original memory." not in html
    assert "archived" in html
    assert "edited" not in html.lower()


def test_god_mode_edit_rejects_blank_summary(client):
    """Blank summaries must be rejected with 422 on the silent edit endpoint."""
    _create_persona(client)
    created = client.post("/api/events/create/", {"summary": "Keep me."})
    node_id = created.json()["node"]["id"]

    response = client.post(f"/api/events/{node_id}/edit/", {"summary": "   "})
    assert response.status_code == 422


def test_god_mode_edit_missing_node_returns_404(client):
    """Editing a nonexistent node must surface 404, never a 500."""
    _create_persona(client)
    response = client.post("/api/events/missing-node/edit/", {"summary": "Bogus."})
    assert response.status_code == 404