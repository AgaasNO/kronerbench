"""Paths and reproducible JSON serialization."""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(Path.cwd() / ".env", override=False)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(dumps(value).encode()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def decode_arguments(raw: str) -> dict[str, Any]:
    value = json.loads(raw, parse_float=Decimal, parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    if not isinstance(value, dict):
        raise ValueError("Tool arguments must be an object.")
    return value
