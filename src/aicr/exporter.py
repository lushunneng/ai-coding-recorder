import json, html, os, tempfile, zipfile, re
from pathlib import Path

def find_session(home:Path, ident:str):
 xs=list(home.glob('sessions/**/metadata.json'))
 if ident=='latest': return max(xs,key=lambda p:p.stat().st_mtime) if xs else None
 for p in xs:
  try:
   if json.loads(p.read_text()).get('id')==ident or p.parent.name==ident:return p
  except Exception: pass
 return None

def derive_events(meta:Path):
    out=meta.with_name('events.jsonl')
    with out.open('w', encoding='utf-8') as f:
        for e in events(meta):
            sem={**e, 'schema_version': 1, 'actor': 'system' if e.get('type') not in {'terminal_input'} else 'user', 'provider': 'generic', 'capture_mode': 'pty', 'stream': 'merged', 'confidence': 'observed'}
            f.write(json.dumps(sem, ensure_ascii=False, separators=(',', ':'))+'\n')

def events(meta:Path):
 raw=meta.with_name('raw.jsonl')
 for line in raw.open('rb'):
  try: yield json.loads(line)
  except Exception: continue

def redact(s:str):
 pats=[(r'(sk-[A-Za-z0-9_-]{10,})','OPENAI_KEY'),(r'(ghp_[A-Za-z0-9]{20,})','GITHUB_TOKEN'),(r'(Bearer\s+)[A-Za-z0-9._~-]+',r'\1REDACTED'),(r'eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+','JWT')]
 for p,repl in pats:s=re.sub(p,repl,s,flags=re.I)
 return s

def payload(e):
 p=e.get('payload',{}); return p.get('text') or p.get('data') or json.dumps(p,ensure_ascii=False)
def render(meta:Path,fmt:str,redact_on=True):
 es=list(events(meta)); title=meta.parent.name
 if not meta.with_name('events.jsonl').exists():
  try: derive_events(meta)
  except OSError: pass
 rows=[]
 for e in es:
  text=payload(e); text=redact(text) if redact_on else text
  rows.append((e['sequence'],e['type'],text))
 if fmt=='json': return json.dumps({'session':json.loads(meta.read_text()),'events':es},ensure_ascii=False,indent=2)
 if fmt=='markdown': return '# AICR Session '+title+'\n\n'+'\n\n'.join(f'## {n}. {t}\n\n```text\n{x}\n```' for n,t,x in rows)
 body=''.join(f'<article><h2>{n}. {html.escape(t)}</h2><pre>{html.escape(x)}</pre></article>' for n,t,x in rows)
 return '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'none\'; img-src data:"><title>AICR Session</title><style>body{font:14px monospace;max-width:1000px;margin:2rem auto}pre{white-space:pre-wrap;background:#f4f4f4;padding:1rem}article{border-bottom:1px solid #ddd}</style>'+body

def atomic_write(path:Path,data:str):
 path.parent.mkdir(parents=True,exist_ok=True); fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.aicr-');
 with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(data);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
