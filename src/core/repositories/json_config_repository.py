"""Raw JSON file repository for lightweight runtime configuration settings."""

import json
import os
import sys
import tempfile
import threading
from typing import Any, Optional

# Sensible fallbacks applied whenever the config file is missing or unreadable.
DEFAULT_CONFIG: dict = {
    "database_path": "agent.db",
    "log_level": "INFO",
    "default_active_node_limit": 20,
    "runtime": {
        "language": "en",
        "timezone": "UTC",
    },
}


class JsonConfigRepository:
    """Reads and writes runtime parameters as a raw JSON file with atomic saves."""

    def __init__(self, config_path: str = "config.json", defaults: Optional[dict] = None) -> None:
        """Store the config file path and the default settings used as a fallback base."""
        self._config_path = config_path
        self._defaults = defaults if defaults is not None else DEFAULT_CONFIG
        self._lock = threading.Lock()

    @property
    def config_path(self) -> str:
        """Return the filesystem path of the managed JSON config file."""
        return self._config_path

    def load(self) -> dict:
        """Return the merged configuration, falling back to defaults when the file is missing or corrupt."""
        with self._lock:
            return self._load_unlocked()

    def save(self, config: dict) -> None:
        """Atomically persist the configuration by replacing the file in one filesystem step."""
        with self._lock:
            self._save_unlocked(config)

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        """Return the value stored under a dotted key path, or default when the key is absent."""
        config = self.load()

        node: Any = config
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default

        return node

    def set(self, key: str, value: Any) -> None:
        """Write a value under a dotted key path and persist the file atomically."""
        with self._lock:
            config = self._load_unlocked()

            node = config
            parts = key.split(".")
            for part in parts[:-1]:
                child = node.get(part)
                if not isinstance(child, dict):
                    child = {}
                    node[part] = child
                node = child

            node[parts[-1]] = value
            self._save_unlocked(config)

    def reset_to_defaults(self) -> None:
        """Overwrite the config file with the built-in default settings."""
        self.save(self._deep_copy(self._defaults))

    def _load_unlocked(self) -> dict:
        """Read the config file without acquiring the lock, merging stored values over defaults."""
        if not os.path.exists(self._config_path):
            return self._deep_copy(self._defaults)

        try:
            with open(self._config_path, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
        except (json.JSONDecodeError, OSError) as read_error:
            print(
                f"Warning: config file '{self._config_path}' is unreadable "
                f"({read_error}). Falling back to default settings.",
                file=sys.stderr,
            )
            return self._deep_copy(self._defaults)

        if not isinstance(data, dict):
            print(
                f"Warning: config file '{self._config_path}' does not contain a JSON "
                "object. Falling back to default settings.",
                file=sys.stderr,
            )
            return self._deep_copy(self._defaults)

        merged = self._deep_copy(self._defaults)
        merged.update(data)
        return merged

    def _save_unlocked(self, config: dict) -> None:
        """Write the config via a temp file and atomic replace, without acquiring the lock."""
        directory = os.path.dirname(os.path.abspath(self._config_path))
        os.makedirs(directory, exist_ok=True)

        file_descriptor, temp_path = tempfile.mkstemp(
            dir=directory,
            prefix=".config-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as file_handle:
                json.dump(config, file_handle, indent=2)
                file_handle.write("\n")
            os.replace(temp_path, self._config_path)
        except Exception:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    @staticmethod
    def _deep_copy(source: dict) -> dict:
        """Return a detached JSON-safe copy of the given settings dictionary."""
        return json.loads(json.dumps(source))
