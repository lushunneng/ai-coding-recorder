from pathlib import Path
import os, typer, shutil, json, hashlib, zipfile, time
from .recorder import record
from .storage import recover_file
from .exporter import find_session, render, atomic_write
app=typer.Typer()
def home():
 p=Path(os.environ.get('AICR_HOME',str(Path.home()/'.aicr'))); p.mkdir(parents=True,exist_ok=True); return p
@app.command()
def record_cmd(command:list[str]=typer.Argument(...,metavar='COMMAND')): raise typer.Exit(record(command,home()))
app.command('record')(record_cmd)
@app.command()
def recover(scan:bool=False):
 for raw in home().glob('sessions/**/raw.jsonl'): recover_file(raw,raw.with_name('metadata.json'),scan)
@app.command()
def show(identifier:str='latest',format:str='summary'):
 m=find_session(home(),identifier)
 if not m: raise typer.BadParameter('session not found')
 if format=='summary': typer.echo(m.read_text()); return
 typer.echo(render(m,'json' if format=='json' else 'markdown'))
@app.command()
def export(identifier:str='latest',format:str='html',out:Path|None=None,bundle:bool=False,force:bool=False,include_raw:bool=False):
 m=find_session(home(),identifier)
 if not m: raise typer.BadParameter('session not found')
 ext='zip' if bundle else format; target=out or home()/'exports'/f'{m.parent.name[:8]}_{int(m.stat().st_mtime)}.{ext}'
 if target.exists() and not force: raise typer.BadParameter('output exists; use --force')
 if bundle:
  target.parent.mkdir(parents=True,exist_ok=True); tmp=target.with_suffix('.tmp.zip')
  with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
   z.writestr('session.html',render(m,'html')); z.writestr('session.md',render(m,'markdown')); z.writestr('manifest.json','{"redacted":true}')
   if include_raw:z.write(m.with_name('raw.jsonl'),'raw.jsonl')
  os.replace(tmp,target)
 else: atomic_write(target,render(m,format))
 typer.echo(str(target))

@app.command("import")
def import_transcript(provider: str = typer.Option(...), file: Path | None = typer.Option(None), transcript: Path | None = typer.Option(None)):
    source = transcript or file
    if source is None: raise typer.BadParameter('provide --file or --transcript')
    if not source.exists(): raise typer.BadParameter("input file not found")
    data = source.read_bytes(); digest = hashlib.sha256(data).hexdigest()
    paths = __import__("aicr.storage", fromlist=["make_session"]).make_session(home())
    meta = {"id": paths.root.name, "status": "completed", "provider": provider, "capture_mode": "import", "source": str(source), "source_sha256": digest, "started_at": time.time(), "ended_at": time.time()}
    paths.raw.write_text(json.dumps({"id":"evt_000000000001","session_id":paths.root.name,"sequence":1,"timestamp":time.time(),"monotonic_ns":time.monotonic_ns(),"type":"terminal_output","payload":{"encoding":"utf-8","text":data.decode("utf-8", errors="replace")}}, ensure_ascii=False)+"\n")
    paths.raw.write_text(paths.raw.read_text()+json.dumps({"id":"evt_000000000002","session_id":paths.root.name,"sequence":2,"timestamp":time.time(),"monotonic_ns":time.monotonic_ns(),"type":"session_end","payload":{"status":"completed"}})+"\n")
    __import__("aicr.storage", fromlist=["atomic_json"]).atomic_json(paths.metadata, meta); typer.echo(paths.root.name)

@app.command()
def init(force:bool=False): home(); typer.echo(str(home()))
if __name__=='__main__': app()
