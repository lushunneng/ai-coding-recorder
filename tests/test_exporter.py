from aicr.exporter import render
from pathlib import Path
import json
def test_html_escapes(tmp_path):
 m=tmp_path/'metadata.json'; m.write_text(json.dumps({'id':'sess_test'})); (tmp_path/'raw.jsonl').write_text(json.dumps({'sequence':1,'type':'terminal_output','payload':{'text':'<script>alert(1)</script>'}})+'\n')
 out=render(m,'html'); assert '<script>alert' not in out and '&lt;script&gt;' in out
