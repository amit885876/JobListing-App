import json,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data/jobs.json'; OUT=ROOT/'dashboard/index.html'
jobs=json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
def esc(x):return html.escape(str(x or ''))
cards=[]
for j in sorted(jobs,key=lambda x:x.get('match',{}).get('score',0),reverse=True):
 m=j.get('match',{});r=''.join(f"<span>✓ {esc(x)}</span>" for x in m.get('reasons',[])[:4]);cards.append(f"<article class='job'><div class='score'>{m.get('score',0)}</div><div><b>{esc(j.get('decision','MAYBE'))}</b> <small>Visa: {esc(j.get('visa',{}).get('status','unknown'))}</small><h2>{esc(j.get('title'))}</h2><div class='company'>{esc(j.get('company'))} · {esc(j.get('location'))}</div><div class='reasons'>{r}</div><a href='{esc(j.get('url','#'))}' target='_blank'>View opening →</a></div></article>")
page=f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Visa Job Radar</title><style>body{{margin:0;background:#0b1020;color:#e8ecf7;font:15px system-ui}}.wrap{{max-width:1050px;margin:auto;padding:36px 20px}}h1{{font-size:34px}}.sub{{color:#9ba6bd}}.job{{display:flex;gap:18px;background:#121a2d;border:1px solid #26314b;border-radius:16px;padding:18px;margin:12px 0}}.score{{font-size:28px;font-weight:800;min-width:55px}}.company{{color:#aeb9d0}}b,small,.reasons span{{font-size:12px;padding:4px 8px;border-radius:8px;background:#202b43}}.reasons{{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}}a{{color:#8ab4ff}}</style></head><body><div class='wrap'><h1>Visa Job Radar</h1><div class='sub'>High-recall backend/software matching · {len(jobs)} retained jobs</div>{''.join(cards) or '<p>No jobs yet. Run the workflow.</p>'}</div></body></html>"
OUT.parent.mkdir(exist_ok=True);OUT.write_text(page,encoding='utf-8')
