import hashlib
import json
import os
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import typer

from .adapters import get_adapter
from .config import ensure as ensure_config
from .config import has_capacity
from .config import load as load_config
from .exporter import atomic_write, events, find_session, payload, render
from .recorder import record
from .storage import RawWriter, atomic_json, make_session, recover_file

app = typer.Typer()
VERSION = "0.1.0"


def version_callback(value: bool):
    if value:
        typer.echo(f"aicr {VERSION}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=version_callback, is_eager=True
    ),
):
    """AI Coding Recorder command line interface."""


def home(create: bool = True):
    p = Path(os.environ.get("AICR_HOME", str(Path.home() / ".aicr")))
    if create:
        p.mkdir(parents=True, exist_ok=True)
    return p


def export_timestamp(meta: Path) -> str:
    try:
        started = json.loads(meta.read_text(encoding="utf-8")).get("started_at")
        return datetime.fromtimestamp(float(started), UTC).strftime("%Y%m%dT%H%M%S")
    except (OSError, ValueError, TypeError, OverflowError):
        return datetime.fromtimestamp(meta.stat().st_mtime, UTC).strftime(
            "%Y%m%dT%H%M%S"
        )


@app.command("record")
def record_cmd(command: list[str] = typer.Argument(..., metavar="COMMAND")):  # noqa: B008
    root = home()
    try:
        config = load_config(root)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    if not has_capacity(root, config):
        raise typer.Exit(code=11)
    return record(command, root)


@app.command()
def recover(scan: bool = False):
    for raw in home().glob("sessions/**/raw.jsonl"):
        recover_file(raw, raw.with_name("metadata.json"), scan)


@app.command("sessions")
def sessions(
    status: str | None = typer.Option(None),
    limit: int = typer.Option(20, min=1, max=1000),
    cursor: str | None = typer.Option(None),
):
    """List recorded sessions in deterministic newest-first order."""
    rows = []
    for meta in home().glob("sessions/**/metadata.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if status and data.get("status") != status:
            continue
        sid = str(data.get("id", meta.parent.name))
        rows.append((str(data.get("started_at", "")), sid, data))
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    if cursor:
        rows = [row for row in rows if row[1] < cursor]
    for _, sid, data in rows[:limit]:
        typer.echo(
            f"{sid}\t{data.get('status', 'unknown')}\t{data.get('provider', 'generic')}"
        )


@app.command()
def doctor():
    """Check local runtime and storage prerequisites without modifying files."""
    root = home(create=False)
    try:
        load_config(root, create=False)
        config_ok = True
    except ValueError as exc:
        typer.echo(str(exc))
        config_ok = False
    checks = {
        "python": True,
        "pty": hasattr(os, "openpty"),
        "home_exists": root.is_dir(),
        "home_writable": root.is_dir() and os.access(root, os.W_OK),
        "config": config_ok,
    }
    for name, ok in checks.items():
        typer.echo(f"{name}: {'ok' if ok else 'error'}")
    if not all(checks.values()):
        raise typer.Exit(code=1)


@app.command()
def show(identifier: str = typer.Argument("latest"), format: str = "summary"):
    m = find_session(home(), identifier)
    if not m:
        raise typer.BadParameter("session not found")
    if format == "summary":
        typer.echo(m.read_text())
        return
    if format == "transcript":
        for event in events(m):
            if event.get("type") in {"terminal_output", "terminal_input"}:
                typer.echo(payload(event))
        return
    if format != "json":
        raise typer.BadParameter("format must be summary, transcript, or json")
    typer.echo(render(m, "json"))


@app.command()
def export(
    identifier: str = typer.Argument("latest"),
    format: str = "html",
    out: Path | None = None,
    bundle: bool = False,
    force: bool = False,
    include_raw: bool = False,
):
    m = find_session(home(), identifier)
    if not m:
        raise typer.BadParameter("session not found")
    if format not in {"html", "markdown", "json"}:
        raise typer.BadParameter("format must be html, markdown, or json")
    if bundle and format != "html":
        raise typer.BadParameter("--bundle cannot be combined with --format")
    if include_raw and not bundle:
        raise typer.BadParameter("--include-raw requires --bundle")
    if include_raw and not force:
        raise typer.BadParameter("--include-raw requires --force confirmation")
    ext = "zip" if bundle else format
    target = (
        out or home() / "exports" / f"{m.parent.name[:8]}_{export_timestamp(m)}.{ext}"
    )
    if target.exists() and not force:
        raise typer.BadParameter("output exists; use --force")
    if bundle:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp.zip")
        html_data = render(m, "html")
        markdown_data = render(m, "markdown")
        manifest = {
            "session_id": m.parent.name,
            "generator_version": VERSION,
            "redacted": not include_raw,
            "files": {
                "session.html": hashlib.sha256(html_data.encode()).hexdigest(),
                "session.md": hashlib.sha256(markdown_data.encode()).hexdigest(),
            },
        }
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("session.html", html_data)
            z.writestr("session.md", markdown_data)
            if include_raw:
                raw_data = m.with_name("raw.jsonl").read_bytes()
                z.writestr("raw.jsonl", raw_data)
                manifest["files"]["raw.jsonl"] = hashlib.sha256(raw_data).hexdigest()
            z.writestr("manifest.json", json.dumps(manifest, indent=2))
        os.replace(tmp, target)
    else:
        atomic_write(target, render(m, format))
    typer.echo(str(target))


@app.command("import")
def import_transcript(
    provider: str = typer.Option(...),
    file: Path | None = typer.Option(None),  # noqa: B008
    transcript: Path | None = typer.Option(None),  # noqa: B008
):
    source = transcript or file
    if source is None:
        raise typer.BadParameter("provide --file or --transcript")
    if not source.exists():
        raise typer.BadParameter("input file not found")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    for existing in home().glob("sessions/**/metadata.json"):
        try:
            if (
                json.loads(existing.read_text(encoding="utf-8")).get("source_sha256")
                == digest
            ):
                raise typer.BadParameter(
                    f"transcript already imported as {existing.parent.name}"
                )
        except (OSError, ValueError, TypeError):
            continue
    adapter_cls = get_adapter(provider)
    if not adapter_cls.capabilities.import_mode:
        raise typer.BadParameter(
            f"provider '{provider}' does not support transcript import"
        )
    text = source.read_text(encoding="utf-8", errors="replace")
    paths = make_session(home())
    meta = {
        "id": paths.root.name,
        "status": "completed",
        "provider": provider,
        "capture_mode": "import",
        "source": str(source),
        "source_sha256": digest,
        "started_at": time.time(),
        "ended_at": time.time(),
        "event_count": 2,
    }
    writer = RawWriter(paths.raw)
    writer.write("terminal_output", {"encoding": "utf-8", "text": text}, actor="user")
    writer.write("session_end", {"status": "completed"})
    writer.close()
    atomic_json(paths.metadata, meta)
    typer.echo(paths.root.name)


@app.command()
def init(force: bool = False):
    root = home()
    ensure_config(root, force=force)
    typer.echo(str(root))


@app.command()
def rebuild_index():
    from .database import rebuild

    typer.echo(f"indexed events: {rebuild(home())}")


@app.command()
def delete(identifier: str, include_assets: bool = False, yes: bool = False):
    import shutil

    from .exporter import find_session

    if not yes:
        raise typer.BadParameter("pass --yes to confirm deletion")
    m = find_session(home(), identifier)
    if not m:
        raise typer.BadParameter("session not found")
    shutil.rmtree(m.parent)
    from .database import rebuild

    rebuild(home())
    typer.echo(f"deleted {m.parent.name}")


@app.command()
def prune(dry_run: bool = True, yes: bool = False):
    try:
        config = load_config(home())
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    metas = []
    for meta in home().glob("sessions/**/metadata.json"):
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            metas.append((float(data.get("ended_at", data.get("started_at", 0))), meta))
        except (OSError, ValueError, TypeError):
            continue
    candidates: list[Path] = []
    if config.max_sessions is not None and len(metas) > config.max_sessions:
        metas.sort(key=lambda item: item[0])
        candidates.extend(meta for _, meta in metas[: len(metas) - config.max_sessions])
    for meta in candidates:
        typer.echo(str(meta.parent.name))
    if candidates and not dry_run and yes:
        import shutil

        for meta in candidates:
            shutil.rmtree(meta.parent)
        from .database import rebuild

        rebuild(home())


@app.command()
def providers():
    from .adapters import ADAPTERS

    for name, cls in ADAPTERS.items():
        typer.echo(
            f"{name}: pty={cls.capabilities.pty} native={cls.capabilities.native} import={cls.capabilities.import_mode}"
        )


@app.command()
def search(query: str, limit: int = 20):
    from .database import search as db_search

    for sid, eid, snippet in db_search(home(), query, limit):
        typer.echo(f"{sid} {eid}: {snippet}")


@app.command()
def control():
    typer.echo("external control is not enabled in this build")
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
