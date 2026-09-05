from pathlib import Path
import typer
from .recorder import record
from .storage import recover_file
app=typer.Typer()
def home():
 p=Path(__import__('os').environ.get("AICR_HOME",Path.home()/".aicr")); p.mkdir(parents=True,exist_ok=True); return p
@app.command()
def record_cmd(command:list[str]=typer.Argument(...,metavar="COMMAND")):
 """Record a command. Use: aicr record -- bash"""
 raise typer.Exit(record(command,home()))
app.command("record")(record_cmd)
@app.command()
def recover(scan:bool=False):
 for raw in home().glob("sessions/**/raw.jsonl"):
  recover_file(raw,raw.with_name("metadata.json"),scan)
if __name__ == "__main__": app()
