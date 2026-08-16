import json
from pathlib import Path
from datetime import datetime, timezone
from app.config import load_yaml
from app.collectors.github_markdown import collect as collect_github_markdown
from app.collectors.amazon import collect as collect_amazon
from app.collectors.company_careers import collect as collect_company_careers
from app.matcher.scorer import score_job
from app.storage import load_jobs, save_jobs
from app.notifications.telegram import notify_new_jobs

ROOT = Path(__file__).resolve().parents[1]
COLLECTORS = {'github_markdown': collect_github_markdown, 'amazon': collect_amazon, 'company_careers': collect_company_careers}


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')


def run_pipeline():
    p = load_yaml(ROOT / 'config/profile.yaml')['candidate']
    sources = load_yaml(ROOT / 'config/sources.yaml')['sources']
    now = datetime.now(timezone.utc).isoformat()

    # PHASE 1: collect first. Nothing is filtered here.
    raw = []
    source_health = []
    for s in sources:
        if not s.get('enabled'):
            continue
        collector = COLLECTORS.get(s.get('type'))
        if not collector:
            source_health.append({'source': s.get('id'), 'status': 'unsupported', 'discovered': 0})
            continue
        try:
            result = collector({**s, 'registry_path': str(ROOT / s.get('registry_path', 'data/companies.json'))})
            if isinstance(result, dict) and 'jobs' in result:
                batch = result.get('jobs', [])
                raw.extend(batch)
                if result.get('health'):
                    source_health.extend(result['health'])
                else:
                    source_health.append({'source': s.get('id'), 'status': 'ok' if batch else 'zero_results', 'discovered': len(batch)})
            else:
                batch = result or []
                raw.extend(batch)
                source_health.append({'source': s.get('id'), 'status': 'ok' if batch else 'zero_results', 'discovered': len(batch)})
        except Exception as exc:
            source_health.append({'source': s.get('id'), 'status': 'error', 'discovered': 0, 'error': f'{type(exc).__name__}: {str(exc)[:200]}'})

    # Persist raw data BEFORE any relevance filtering so collection failures are visible.
    _write_json(ROOT / 'data/raw_jobs.json', {'collected_at': now, 'count': len(raw), 'jobs': raw})
    _write_json(ROOT / 'data/source_health.json', {'checked_at': now, 'sources': source_health})

    # PHASE 2: normalize, score and filter for the candidate.
    existing = load_jobs(ROOT / 'data/jobs.json')
    by = {}
    for old in existing:
        x = score_job(old, p)
        if x['decision'] != 'SKIP':
            by[x['dedupe_key']] = x

    new = []
    for j in raw:
        x = score_job(j, p)
        if x['decision'] == 'SKIP' or not x.get('url'):
            continue
        if x['dedupe_key'] not in by:
            x['status'] = 'new'
            x['first_seen'] = x['last_seen']
            by[x['dedupe_key']] = x
            new.append(x)
        else:
            by[x['dedupe_key']].update(x)

    jobs = sorted(by.values(), key=lambda x: x.get('match', {}).get('score', 0), reverse=True)
    save_jobs(ROOT / 'data/jobs.json', jobs)
    notify_new_jobs(new)
    return {'processed': len(raw), 'new': len(new), 'kept': len(jobs), 'sources': len(sources), 'health_entries': len(source_health)}
