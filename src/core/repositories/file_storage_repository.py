"""Raw file storage repository for unmanaged image resources on disk."""

import base64
import os
import uuid
from typing import Optional

# 1x1 gray PNG used as the avatar placeholder until an image is generated.
PLACEHOLDER_AVATAR_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGND8v"
    "H+fwAH1gMLpApMnQAAAABJRU5ErkJggg=="
)

# Reserved name that resolves to the placeholder avatar bytes.
PLACEHOLDER_NAME = "__placeholder__"

# Magic byte prefixes of the image formats accepted for uploads.
_ALLOWED_IMAGE_PREFIXES = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF8",  # GIF87a/GIF89a
    b"RIFF",  # WebP (RIFF container)
)


class FileStorageRepository:
    """Stores raw bytes under generated filenames inside a single root folder."""

    def __init__(self, root_path: str) -> None:
        """Create the storage root folder when it does not exist yet."""
        self._root = root_path
        os.makedirs(self._root, exist_ok=True)

    def save_bytes(self, original_filename: str, data: bytes) -> str:
        """Persist raw bytes under a collision-safe generated filename."""
        extension = os.path.splitext(original_filename)[1].lower()[:10]
        stored_filename = f"{uuid.uuid4().hex}{extension}"
        self.write_bytes(stored_filename, data)
        return stored_filename

    def write_bytes(self, filename: str, data: bytes) -> None:
        """Write bytes to the given filename inside the storage root."""
        self._require_safe_name(filename)
        target_path = os.path.join(self._root, filename)
        with open(target_path, "wb") as file_handle:
            file_handle.write(data)

    def open(self, filename: str) -> Optional[bytes]:
        """Return the stored bytes, the placeholder for the reserved name, or None."""
        if filename == PLACEHOLDER_NAME:
            return PLACEHOLDER_AVATAR_PNG

        self._require_safe_name(filename)
        target_path = os.path.join(self._root, filename)
        if not os.path.isfile(target_path):
            return None

        with open(target_path, "rb") as file_handle:
            return file_handle.read()

    def delete(self, filename: str) -> None:
        """Remove the stored file if present."""
        self._require_safe_name(filename)
        target_path = os.path.join(self._root, filename)
        if os.path.isfile(target_path):
            os.remove(target_path)

    def is_allowed_image(self, data: bytes) -> bool:
        """Return True when the byte signature matches an accepted image format."""
        return any(data.startswith(prefix) for prefix in _ALLOWED_IMAGE_PREFIXES)

    def _require_safe_name(self, filename: str) -> None:
        """Reject path traversal and nested paths inside stored filenames."""
        if (
            not filename
            or os.path.basename(filename) != filename
            or filename in (".", "..")
            or "\\" in filename
        ):
            raise ValueError(f"Unsafe storage filename: {filename!r}")
