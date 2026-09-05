from pathlib import Path
import os, typer, shutil
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
 ext='zip' if bundle else format; target=out or home()/'exports'/f'{m.parent.name[:8]}_{m.stat().st_mtime_ns}.{ext}'
 if target.exists() and not force: raise typer.BadParameter('output exists; use --force')
 if bundle:
  target.parent.mkdir(parents=True,exist_ok=True); tmp=target.with_suffix('.tmp.zip')
  with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
   z.writestr('session.html',render(m,'html')); z.writestr('session.md',render(m,'markdown')); z.writestr('manifest.json','{"redacted":true}')
   if include_raw:z.write(m.with_name('raw.jsonl'),'raw.jsonl')
  os.replace(tmp,target)
 else: atomic_write(target,render(m,format))
 typer.echo(str(target))
@app.command()
def init(force:bool=False): home(); typer.echo(str(home()))
if __name__=='__main__': app()
