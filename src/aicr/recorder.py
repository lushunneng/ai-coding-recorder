import os
import pty
import select
import signal
import time
from pathlib import Path

from .storage import RawWriter, SessionLock, atomic_json, make_session


def record(command: list[str], home: Path) -> int:
    paths = make_session(home)
    lock = SessionLock(paths.lock, paths.root.name)
    lock.acquire()
    writer = RawWriter(paths.raw)
    meta = {
        "id": paths.root.name,
        "status": "running",
        "command": command,
        "cwd": os.getcwd(),
        "started_at": time.time(),
        "capture_mode": "pty",
    }
    atomic_json(paths.metadata, meta)
    master, pid = pty.fork()
    if pid == 0:
        os.setsid()
        os.execvp(command[0], command)
    writer.write("session_start", {"argv": command, "cwd": os.getcwd()})
    old = {
        s: signal.getsignal(s) for s in (signal.SIGWINCH, signal.SIGTERM, signal.SIGHUP)
    }

    def forward(sig, _):
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            pass

    for s in old:
        signal.signal(s, forward)
    poller = select.poll()
    poller.register(master, select.POLLIN)
    if os.isatty(0):
        poller.register(0, select.POLLIN)
    try:
        while True:
            ready = poller.poll(200)
            r = [fd for fd, _ in ready]
            if 0 in r:
                b = os.read(0, 4096)
                if not b:
                    break
                os.write(master, b)
                writer.write(
                    "terminal_input",
                    {
                        "encoding": "base64",
                        "data": __import__("base64").b64encode(b).decode(),
                    },
                )
            if master in r:
                try:
                    b = os.read(master, 65536)
                except OSError:
                    b = b""
                if b:
                    os.write(1, b)
                    writer.write(
                        "terminal_output",
                        {
                            "encoding": "base64",
                            "data": __import__("base64").b64encode(b).decode(),
                        },
                    )
                else:
                    break
            lock.heartbeat()
        try:
            _, status = os.waitpid(pid, 0)
            code = os.waitstatus_to_exitcode(status)
        except ChildProcessError:
            code = 0
        writer.write("process_exit", {"returncode": code})
        writer.write("session_end", {"status": "completed" if code == 0 else "failed"})
        meta.update(
            status="completed" if code == 0 else "failed",
            ended_at=time.time(),
            returncode=code,
            event_count=writer.sequence,
        )
        atomic_json(paths.metadata, meta)
        return code
    except BaseException as e:
        writer.write("error", {"error": type(e).__name__, "message": str(e)})
        meta.update(
            status="interrupted", ended_at=time.time(), event_count=writer.sequence
        )
        atomic_json(paths.metadata, meta)
        raise
    finally:
        writer.close()
        try:
            os.close(master)
        except OSError:
            pass
        lock.release()
