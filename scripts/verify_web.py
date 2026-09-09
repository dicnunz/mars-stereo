"""Validate the browser bundle against the original scientific artifacts."""
from pathlib import Path
import hashlib,json,re,subprocess,csv
ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'web'
def check():
 d=json.loads((W/'data.js').read_text().removeprefix('window.DATA=').removesuffix(';\n'))
 for x in json.loads((W/'sources.json').read_text())['sources']:
  expected=x['sha256'];assert hashlib.sha256((ROOT/x['source']).read_bytes()).hexdigest()==expected,x['source']
  if 'asset' in x:assert hashlib.sha256((W/x['asset']).read_bytes()).hexdigest()==expected,x['asset']
 for x in d['items']:
  if 'asset' in x:assert (W/x['asset']).is_file()
 assert d['items']
 html=(W/'index.html').read_text()
 for url in re.findall(r'(?:src|href)="([^"]+)"',html):
  if not url.startswith(('https:','#')):assert (W/url).exists(),url
 if d['kind']=='eht':
  import numpy as np
  assert len(d['items'])==8
  for i,x in enumerate(d['items']):
   m=json.loads((ROOT/f'results/stage_{i}/metrics.json').read_text())
   assert x['metrics'][1][1]==m['visibilities']
   if i<6:assert np.array_equal(x['pixels'],np.load(ROOT/f'results/stage_{i}/arrays.npz')['restored'].flatten())
   else:assert x['pixels'] is None and m['status']=='no_reconstruction'
  assert d['maximum']==float(np.load(ROOT/'results/stage_0/arrays.npz')['restored'].max())
 if d['kind']=='apollo':
  original=json.loads((ROOT/'results/bench/dsky.json').read_text());by_cycle={x['cycle']:x for x in original}
  for x in d['items']:
   s=by_cycle[x['metrics'][0][1]]
   for k,v in x['state'].items():assert v==s['signs'].get(k,'')+s[k]
  assert any(x['state']['R1'].strip().lstrip('+')=='01406' for x in d['items'])
 for f in ['data.js','app.js']:subprocess.run(['node','--check',str(W/f)],check=True)
 print(f'{ROOT.name}: {len(d["items"])} records, assets and source digests verified; JavaScript syntax valid')
if __name__=='__main__':check()
