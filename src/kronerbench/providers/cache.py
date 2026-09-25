"""Persist request/response bodies only. HTTP headers never enter this store."""

import json
import sqlite3
from pathlib import Path
from typing import Any

from kronerbench.config import digest, dumps


class Cache:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, request TEXT NOT NULL, response TEXT NOT NULL)"
        )
        self.db.commit()

    def get(self, request: dict[str, Any]) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT response FROM responses WHERE key=?", (digest(request),)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, request: dict[str, Any], response: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO responses VALUES (?,?,?)",
            (digest(request), dumps(request), dumps(response)),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()
