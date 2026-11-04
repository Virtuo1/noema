"""Application configuration and local-first defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_OWNER_USER_ID = "u_local_owner"
DEFAULT_OWNER_DISPLAY_NAME = "Local User"


@dataclass(slots=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: os.environ.get("NOEMA_DATABASE_URL", "sqlite:///./data/noema.db")
    )
    secrets_file_path: str = field(
        default_factory=lambda: os.environ.get(
            "NOEMA_SECRETS_FILE", str(Path.home() / ".config" / "noema" / "secrets.json")
        )
    )
    export_dir: str = field(
        default_factory=lambda: os.environ.get("NOEMA_EXPORT_DIR", "./exports")
    )
    host: str = field(default_factory=lambda: os.environ.get("NOEMA_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("NOEMA_PORT", "8000")))
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.environ.get(
                "NOEMA_ALLOWED_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000",
            ).split(",")
            if origin.strip()
        ]
    )
    enable_background_worker: bool = field(
        default_factory=lambda: os.environ.get("NOEMA_ENABLE_WORKER", "1") == "1"
    )
    worker_poll_interval_seconds: float = field(
        default_factory=lambda: float(os.environ.get("NOEMA_WORKER_POLL_SECONDS", "0.5"))
    )


def get_settings() -> Settings:
    return Settings()
