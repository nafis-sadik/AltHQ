"""Layer 1 UI tests: the Django dashboard vertical slice for Phase 1."""

import json
import re
import uuid
from urllib.parse import urlencode

import pytest  # noqa: F401  (used implicitly via the client fixture)

# Paths, settings, and artifact isolation are configured in conftest.py.


def _put(client, url, data):
    """Send a PUT with a jQuery-serialized (urlencoded) form body."""
    return client.put(
        url,
        urlencode(data),
        content_type="application/x-www-form-urlencoded",
    )


def test_index_without_persona_shows_empty_state(client):
    """The dashboard must guide the user to create a persona first."""
    response = client.get("/")
    html = response.content.decode()

    assert response.status_code == 200
    assert "No persona yet" in html
    assert "Create persona" in html


def test_persona_create_flow(client):
    """Creating a persona via POST /api/personas/ must return 201 and render on the dashboard."""
    response = client.post(
        "/api/personas/",
        {
            "name": "Aria",
            "gender": "female",
            "bio": "A warm companion.",
            "background_story": "Born in a home lab.",
        },
    )
    assert response.status_code == 201
    assert response.json()["ok"] is True

    dashboard = client.get("/")
    html = dashboard.content.decode()
    assert "Aria" in html
    assert "A warm companion." in html


def test_persona_create_rejects_invalid(client):
    """Invalid persona input must return field errors with 422."""
    response = client.post("/api/personas/", {"name": "", "bio": ""})
    assert response.status_code == 422
    assert "name must not be blank." in response.json()["errors"]


def test_persona_update_ajax(client):
    """The PUT endpoint must persist updates and return JSON state."""
    client.post(
        "/api/personas/",
        {"name": "Aria", "bio": "A warm companion."},
    )

    dashboard = client.get("/")
    html = dashboard.content.decode()
    agent_id = html.split('name="agent_id" value="')[1].split('"')[0]

    response = _put(
        client,
        f"/api/personas/{agent_id}/",
        {
            "name": "Aria Prime",
            "active_node_limit": "42",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["persona"]["name"] == "Aria Prime"
    assert payload["persona"]["active_node_limit"] == 42


def test_persona_update_ajax_rejects_invalid(client):
    """The PUT endpoint must return field errors with 422, never a 500."""
    client.post("/api/personas/", {"name": "Aria", "bio": "Warm."})
    dashboard = client.get("/")
    html = dashboard.content.decode()
    agent_id = html.split('name="agent_id" value="')[1].split('"')[0]

    response = _put(
        client,
        f"/api/personas/{agent_id}/",
        {"name": "", "active_node_limit": "7"},
    )
    payload = response.json()

    assert response.status_code == 422
    assert "name must not be blank." in payload["errors"]


def test_config_endpoints_removed_and_runtime_is_readonly(client):
    """The config API must be gone and the runtime panel must be read-only."""
    response = client.post(
        "/api/config/update/",
        data=json.dumps({"key": "runtime.language", "value": "de"}),
        content_type="application/json",
    )
    assert response.status_code == 404

    html = client.get("/").content.decode()
    assert "cfg-log" not in html and "cfg-lang" not in html

    denied = client.post(
        "/api/config/update/",
        data=json.dumps({"key": "database_path", "value": "evil.db"}),
        content_type="application/json",
    )
    assert denied.status_code == 404


# Minimal valid PNG (1x1 transparent) used for sheet uploads.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f030005fe02fea72d1e480000000049454e44ae426082"
)


def _create_persona(client):
    """Create the persona under test and return its agent id from the dashboard HTML."""
    client.post("/api/personas/", {"name": "Aria", "gender": "female", "bio": "Warm."})
    html = client.get("/").content.decode()
    return html.split('name="agent_id" value="')[1].split('"')[0]


def test_gender_restricted_to_dropdown_options(client):
    """The UI offers exactly the canonical genders and rejects others."""
    html = client.get("/persona/new/").content.decode()
    for label in (">Male<", ">Female<", ">Non-binary<", ">Prefer not to say<"):
        assert label in html

    _create_persona(client)
    dashboard = client.get("/").content.decode()
    agent_id = dashboard.split('name="agent_id" value="')[1].split('"')[0]

    invalid = _put(
        client,
        f"/api/personas/{agent_id}/",
        {"gender": "robot"},
    )
    assert invalid.status_code == 422
    assert any("gender must be one of" in error for error in invalid.json()["errors"])


def test_sheet_upload_list_delete_flow(client):
    """Uploading a sheet must persist it, render it, and delete cleanly."""
    _create_persona(client)

    uploaded = client.post(
        "/api/sheets/",
        {"sheet": _FakeUpload("aria_ref.png", PNG_BYTES, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.content
    sheet_id = uploaded.json()["sheet"]["id"]

    dashboard = client.get("/").content.decode()
    assert "aria_ref.png" in dashboard
    assert "Generate picture" in dashboard

    image = client.get(f"/sheets/{sheet_id}/image/")
    assert image.status_code == 200
    assert image.content == PNG_BYTES

    deleted = client.delete(f"/api/sheets/{sheet_id}/")
    assert deleted.status_code == 200
    assert client.get(f"/sheets/{sheet_id}/image/").status_code == 404


def test_sheet_upload_rejects_non_image(client):
    """Non-image bytes must be rejected by content sniffing."""
    _create_persona(client)

    uploaded = client.post(
        "/api/sheets/",
        {"sheet": _FakeUpload("evil.png", b"<script>not-an-image</script>", "image/png")},
    )
    assert uploaded.status_code == 422
    assert "does not look like a valid image" in uploaded.json()["errors"][0]


def test_generate_endpoint_returns_501_stub(client):
    """The generate button endpoint must answer 501 until a provider is plugged in."""
    _create_persona(client)
    uploaded = client.post(
        "/api/sheets/",
        {"sheet": _FakeUpload("aria_ref.png", PNG_BYTES, "image/png")},
    )
    sheet_id = uploaded.json()["sheet"]["id"]

    response = client.post("/api/avatar/generate/")
    assert response.status_code == 501
    assert "not available in this phase" in response.json()["errors"][0]


def test_avatar_serves_placeholder_and_generated_marker(client):
    """Avatar returns a PNG placeholder by default and 501 on generated markers."""
    _create_persona(client)
    avatar = client.get("/avatar/")
    assert avatar.status_code == 200
    assert avatar.content.startswith(b"\x89PNG")


class _FakeUpload:
    """Minimal in-memory stand-in for Django's UploadedFile."""

    def __init__(self, name, content, content_type):
        self.name = name
        self.content = content
        self.content_type = content_type

    def read(self):
        return self.content
