import json, html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/jobs.json'
HEALTH = ROOT / 'data/source_health.json'
OUT = ROOT / 'dashboard/index.html'
jobs = json.loads(DATA.read_text(encoding='utf-8')) if DATA.exists() else []
health = json.loads(HEALTH.read_text(encoding='utf-8')).get('sources', []) if HEALTH.exists() else []

def esc(x):
    return html.escape(str(x or ''))

cards = []
for j in sorted(jobs, key=lambda x: x.get('match', {}).get('score', 0), reverse=True):
    m = j.get('match', {})
    visa = j.get('visa', {})
    reasons = ''.join(f"<span>✓ {esc(x)}</span>" for x in m.get('reasons', [])[:4])
    url = j.get('url') or '#'
    cards.append(f"<article class='job'><div class='score'>{m.get('score', 0)}/100</div><div class='body'><div><b>{esc(j.get('decision','MAYBE'))}</b> <small>Visa: {esc(visa.get('status','unknown'))}</small></div><h2>{esc(j.get('title'))}</h2><div class='company'>{esc(j.get('company'))} · {esc(j.get('location'))}</div><div class='reasons'>{reasons}</div><a href='{esc(url)}' target='_blank' rel='noopener'>View opening →</a></div></article>")

health_rows = []
for h in health:
    status = h.get('source_status', h.get('status', 'unknown'))
    cls = 'ok' if status == 'ok' else ('bad' if status == 'error' else 'warn')
    health_rows.append(f"<tr><td>{esc(h.get('company', h.get('source')))}</td><td class='{cls}'>{esc(status)}</td><td>{h.get('discovered', 0)}</td><td>{esc(h.get('error',''))}</td></tr>")

page = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Visa Job Radar</title><style>body{{margin:0;background:#0b1020;color:#e8ecf7;font:15px system-ui}}.wrap{{max-width:1150px;margin:auto;padding:32px 20px}}h1{{font-size:34px;margin-bottom:4px}}.sub{{color:#9ba6bd;margin-bottom:24px}}.panel{{background:#121a2d;border:1px solid #26314b;border-radius:16px;padding:18px;margin:16px 0 22px;overflow:auto}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #26314b;text-align:left}}.ok{{color:#5ee38a}}.warn{{color:#ffd166}}.bad{{color:#ff6b6b}}.job{{display:flex;gap:18px;background:#121a2d;border:1px solid #26314b;border-radius:16px;padding:18px;margin:12px 0}}.score{{font-size:28px;font-weight:800;min-width:78px}}.company{{color:#aeb9d0}}b,small,.reasons span{{font-size:12px;padding:4px 8px;border-radius:8px;background:#202b43}}.reasons{{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0}}a{{color:#8ab4ff}}h2{{margin:8px 0}}</style></head><body><div class='wrap'><h1>Visa Job Radar</h1><div class='sub'>High-recall backend/software matching · {len(jobs)} retained jobs · collection is validated before filtering</div><section class='panel'><h2>Source health</h2><table><thead><tr><th>Company / source</th><th>Status</th><th>Raw jobs</th><th>Error</th></tr></thead><tbody>{''.join(health_rows) or '<tr><td colspan=4>No collection run yet</td></tr>'}</tbody></table></section><h2>Relevant openings</h2>{''.join(cards) or '<p>No relevant jobs yet. Check Source health above before assuming there are no openings.</p>'}</div></body></html>"""
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(page, encoding='utf-8')
