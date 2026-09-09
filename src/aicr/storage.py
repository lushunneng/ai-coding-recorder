import json
import os
import socket
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class SessionPaths:
    root: Path
    raw: Path
    metadata: Path
    lock: Path


class RawWriter:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fp = path.open("ab", buffering=0)
        self.sequence = 0
        self.session_id = self.path.parent.name
        self.writer_id = uuid.uuid4().hex

    def write(self, typ: str, payload: dict, actor: str = "system") -> int:
        self.sequence += 1
        event = {
            "id": f"evt_{uuid.uuid4().hex}",
            "session_id": self.session_id,
            "sequence": self.sequence,
            "timestamp": datetime.now(UTC).isoformat(),
            "monotonic_ns": time.monotonic_ns(),
            "type": typ,
            "payload": payload,
        }
        self.fp.write(
            (
                json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
            ).encode("utf-8")
        )
        if typ in {"session_start", "session_end", "error"}:
            self.fp.flush()
            os.fsync(self.fp.fileno())
        return self.sequence

    def close(self):
        self.fp.flush()
        self.fp.close()


class SessionLock:
    def __init__(self, path: Path, session_id: str):
        self.path, self.session_id = path, session_id
        self.held = False
        self.lock_id: str | None = None

    def acquire(self):
        data = {
            "pid": os.getpid(),
            "process_start_time": time.time(),
            "session_id": self.session_id,
            "created_at": time.time(),
            "heartbeat_at": time.time(),
            "host_id": socket.gethostname(),
            "takeover_id": uuid.uuid4().hex,
        }
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            self.held = True
            self.lock_id = data["takeover_id"]
        except FileExistsError:
            raise RuntimeError("session lock is held") from None

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def is_stale(self, timeout: float = 30.0) -> bool:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            heartbeat = float(data.get("heartbeat_at", 0))
            pid = int(data.get("pid", 0))
        except (OSError, ValueError, TypeError):
            return True
        return (not self._pid_alive(pid)) and time.time() - heartbeat > timeout

    def heartbeat(self):
        if self.held:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("takeover_id") != self.lock_id:
                    self.held = False
                    return
                data["heartbeat_at"] = time.time()
                atomic_json(self.path, data)
            except (OSError, ValueError, TypeError):
                pass

    def takeover(self, timeout: float = 30.0) -> bool:
        """Atomically attempt to replace a stale lock and verify ownership."""
        if self.path.exists() and not self.is_stale(timeout):
            return False
        takeover_id = uuid.uuid4().hex
        data = {
            "pid": os.getpid(),
            "process_start_time": time.time(),
            "session_id": self.session_id,
            "created_at": time.time(),
            "heartbeat_at": time.time(),
            "host_id": socket.gethostname(),
            "takeover_id": takeover_id,
        }
        tmp = self.path.with_name(f".{self.path.name}.{takeover_id}.tmp")
        try:
            with tmp.open("x", encoding="utf-8") as stream:
                json.dump(data, stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
            current = json.loads(self.path.read_text(encoding="utf-8"))
            if current.get("takeover_id") != takeover_id:
                return False
            self.lock_id = takeover_id
            self.held = True
            return True
        except (FileExistsError, OSError, ValueError, TypeError):
            return False
        finally:
            try:
                tmp.unlink()
            except FileNotFoundError:
                pass

    def release(self):
        if self.held:
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("takeover_id") == self.lock_id:
                    self.path.unlink()
            except (FileNotFoundError, OSError, ValueError, TypeError):
                pass
            self.held = False


def make_session(home: Path) -> SessionPaths:
    now = datetime.now(UTC)
    sid = "sess_" + now.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:12]
    root = home / "sessions" / now.strftime("%Y/%m/%d") / sid
    root.mkdir(parents=True, mode=0o700)
    return SessionPaths(root, root / "raw.jsonl", root / "metadata.json", root / "lock")


def atomic_json(path: Path, data: dict):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".metadata.")
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def recover_file(raw: Path, metadata: Path, scan=False):
    valid = []
    skipped = []
    if raw.exists():
        for line in raw.open("rb"):
            try:
                valid.append(json.loads(line))
            except (OSError, ValueError, TypeError):
                if scan:
                    skipped.append(len(valid) + 1)
                else:
                    break
    state = {
        "recovery": {
            "last_valid_sequence": valid[-1]["sequence"] if valid else 0,
            "skipped_sequences": skipped,
            "interrupted": True,
        }
    }
    # Merge recovery state into existing metadata instead of clobbering it.
    if metadata.exists():
        try:
            merged = json.loads(metadata.read_text())
        except (OSError, ValueError, TypeError):
            merged = {}
    else:
        merged = {}
    merged["recovery"] = state["recovery"]
    atomic_json(metadata, merged)
    return state
