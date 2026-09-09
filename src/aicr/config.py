from __future__ import annotations

import os
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = """# AICR local configuration
max_total_bytes = 21474836480
max_session_bytes = 2147483648
redaction_enabled = true
record_input = true
"""


@dataclass(frozen=True)
class Config:
    retention_days: int | None = None
    max_sessions: int | None = None
    max_total_bytes: int = 20 * 1024**3
    max_session_bytes: int = 2 * 1024**3
    redaction_enabled: bool = True
    record_input: bool = True


def path(home: Path) -> Path:
    return home / "config.toml"


def ensure(home: Path, force: bool = False) -> Path:
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = path(home)
    if force or not target.exists():
        target.write_text(DEFAULT_CONFIG, encoding="utf-8")
        os.chmod(target, 0o600)
    return target


def load(home: Path, create: bool = True) -> Config:
    target = ensure(home) if create else path(home)
    if not target.exists():
        return Config()
    try:
        values = tomllib.loads(target.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid configuration {target}: {exc}") from exc
    allowed = set(Config.__dataclass_fields__)
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(
            f"unknown configuration field(s) in {target}: {sorted(unknown)}"
        )
    try:
        return Config(**values)
    except TypeError as exc:
        raise ValueError(f"invalid configuration {target}: {exc}") from exc


def total_bytes(home: Path) -> int:
    total = 0
    for item in home.glob("sessions/**"):
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def has_capacity(home: Path, config: Config) -> bool:
    usage = shutil.disk_usage(home)
    return total_bytes(home) < config.max_total_bytes and usage.free > 0
