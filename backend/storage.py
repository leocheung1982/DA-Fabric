"""
Storage layer — JSON file persistence with optional SQLite cache.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

DATA_FILES = {
    "nodes": "nodes.json",
    "resources": "resources.json",
    "demands": "demands.json",
    "semantic_mappings": "semantic_mappings.json",
    "ground_truth": "ground_truth.json",
    "feedback_events": "feedback_events.json",
    "proactive_events": "proactive_events.json",
}


class StorageManager:
    """Manages JSON persistence and optional SQLite index."""

    def __init__(self, data_dir: Path, use_sqlite: bool = False) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.use_sqlite = use_sqlite
        self._db_path = self.data_dir / "dafabric_cache.db"
        if use_sqlite:
            self._init_sqlite()

    def _init_sqlite(self) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
        conn.close()

    def path_for(self, name: str) -> Path:
        filename = DATA_FILES.get(name, name)
        return self.data_dir / filename

    def exists(self, name: str) -> bool:
        return self.path_for(name).exists()

    def read_json(self, name: str, default: Any = None) -> Any:
        path = self.path_for(name)
        if not path.exists():
            return default if default is not None else []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, name: str, data: Any) -> None:
        path = self.path_for(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        if self.use_sqlite:
            self._cache_json(name, data)

    def append_json_record(self, name: str, record: dict) -> None:
        """Append a single record to a JSON list file."""
        data = self.read_json(name, default=[])
        if not isinstance(data, list):
            data = []
        data.append(record)
        self.write_json(name, data)

    def _cache_json(self, key: str, data: Any) -> None:
        conn = sqlite3.connect(self._db_path)
        conn.execute(
            "INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
            (key, json.dumps(data, default=str)),
        )
        conn.commit()
        conn.close()

    def read_cached(self, key: str) -> Optional[Any]:
        if not self.use_sqlite or not self._db_path.exists():
            return None
        conn = sqlite3.connect(self._db_path)
        row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
        conn.close()
        if row:
            return json.loads(row[0])
        return None
