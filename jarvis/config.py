"""Application settings. Everything configurable lives here (and in env vars)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    host: str = "127.0.0.1"
    port: int = 8000
    knowledge_dir: Path = ROOT / "knowledge"
    data_dir: Path = ROOT / "data"  # saved chats live in data/chats/
    max_tool_rounds: int = 4      # how many tool calls Jarvis may chain per reply
    max_history: int = 16         # how many past messages are sent to the model
    request_timeout: int = 180    # seconds to wait for the local model

    @classmethod
    def from_env(cls) -> "Settings":
        """Override defaults with JARVIS_* environment variables."""
        defaults = cls()
        return cls(
            model=os.getenv("JARVIS_MODEL", defaults.model),
            ollama_url=os.getenv("JARVIS_OLLAMA_URL", defaults.ollama_url).rstrip("/"),
            host=os.getenv("JARVIS_HOST", defaults.host),
            port=int(os.getenv("JARVIS_PORT", defaults.port)),
            knowledge_dir=Path(os.getenv("JARVIS_KNOWLEDGE_DIR", defaults.knowledge_dir)),
            data_dir=Path(os.getenv("JARVIS_DATA_DIR", defaults.data_dir)),
        )
