from pathlib import Path
from app.config import load_yaml
from app.collectors.github_markdown import collect
from app.matcher.scorer import score_job
from app.storage import load_jobs,save_jobs
from app.notifications.telegram import notify_new_jobs
ROOT=Path(__file__).resolve().parents[1]

def run_pipeline():
    p=load_yaml(ROOT/'config/profile.yaml')['candidate']
    sources=load_yaml(ROOT/'config/sources.yaml')['sources']
    existing=load_jobs(ROOT/'data/jobs.json')
    by={}
    # Re-score existing jobs so tightened rules immediately remove old irrelevant roles.
    for old in existing:
        x=score_job(old,p)
        if x['decision']!='SKIP': by[x['dedupe_key']]=x
    raw=[]
    for s in sources:
        if s.get('enabled'):
            try: raw += collect(s)
            except Exception as e: print(f'Source failed: {s["id"]}: {e}')
    new=[]
    for j in raw:
        x=score_job(j,p)
        if x['decision']=='SKIP': continue
        if x['dedupe_key'] not in by:
            x['status']='new'; x['first_seen']=x['last_seen']; by[x['dedupe_key']]=x; new.append(x)
        else:
            by[x['dedupe_key']].update(x)
    jobs=sorted(by.values(),key=lambda x:x.get('match',{}).get('score',0),reverse=True)
    save_jobs(ROOT/'data/jobs.json',jobs)
    notify_new_jobs(new)
    return {'processed':len(raw),'new':len(new),'kept':len(jobs)}
