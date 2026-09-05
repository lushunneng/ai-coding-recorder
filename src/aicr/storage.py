import json, os, tempfile, time
from pathlib import Path
from dataclasses import dataclass

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
    def write(self, typ: str, payload: dict, actor: str = "system") -> int:
        self.sequence += 1
        event = {"id": f"evt_{self.sequence:012d}", "session_id": self.path.parent.name, "sequence": self.sequence, "timestamp": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(), "monotonic_ns": time.monotonic_ns(), "type": typ, "payload": payload}
        self.fp.write((json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        if typ in {"session_start", "session_end", "error"}: self.fp.flush(); os.fsync(self.fp.fileno())
        return self.sequence
    def close(self):
        self.fp.flush(); self.fp.close()

class SessionLock:
    def __init__(self, path: Path, session_id: str): self.path, self.session_id = path, session_id; self.held = False
    def acquire(self):
        data = {"pid": os.getpid(), "process_start_time": time.time(), "session_id": self.session_id, "created_at": time.time(), "heartbeat_at": time.time(), "host_id": __import__('socket').gethostname(), "takeover_id": None}
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, json.dumps(data).encode()); os.close(fd); self.held = True
        except FileExistsError: raise RuntimeError("session lock is held")
    def heartbeat(self):
        if self.held:
            try:
                data=json.loads(self.path.read_text()); data["heartbeat_at"]=time.time(); self.path.write_text(json.dumps(data)); os.chmod(self.path,0o600)
            except OSError: pass
    def release(self):
        if self.held:
            try: self.path.unlink()
            except FileNotFoundError: pass
            self.held=False

def make_session(home: Path) -> SessionPaths:
    now=__import__('datetime').datetime.now(__import__('datetime').timezone.utc)
    sid="sess_"+now.strftime("%Y%m%dT%H%M%S")+f"_{os.getpid()}"
    root=home/"sessions"/now.strftime("%Y/%m/%d")/sid; root.mkdir(parents=True, mode=0o700)
    return SessionPaths(root,root/"raw.jsonl",root/"metadata.json",root/"lock")

def atomic_json(path: Path, data: dict):
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".metadata."); os.fchmod(fd,0o600)
    with os.fdopen(fd,"w") as f: json.dump(data,f,ensure_ascii=False,indent=2); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,path)

def recover_file(raw: Path, metadata: Path, scan=False):
    valid=[]; skipped=[]
    for line in raw.open("rb"):
        try: valid.append(json.loads(line))
        except Exception:
            if scan: skipped.append(len(valid)+1)
            else: break
    state={"recovery":{"last_valid_sequence": valid[-1]["sequence"] if valid else 0,"skipped_sequences":skipped,"interrupted":True}}
    atomic_json(metadata,state); return state
