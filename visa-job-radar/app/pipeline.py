from pathlib import Path
from app.config import load_yaml
from app.collectors.github_markdown import collect as collect_github_markdown
from app.collectors.amazon import collect as collect_amazon
from app.collectors.company_careers import collect as collect_company_careers
from app.matcher.scorer import score_job
from app.storage import load_jobs,save_jobs
from app.notifications.telegram import notify_new_jobs
ROOT=Path(__file__).resolve().parents[1]
COLLECTORS={'github_markdown':collect_github_markdown,'amazon':collect_amazon,'company_careers':collect_company_careers}

def run_pipeline():
    p=load_yaml(ROOT/'config/profile.yaml')['candidate']
    sources=load_yaml(ROOT/'config/sources.yaml')['sources']
    existing=load_jobs(ROOT/'data/jobs.json'); by={}
    for old in existing:
        x=score_job(old,p)
        if x['decision']!='SKIP': by[x['dedupe_key']]=x
    raw=[]
    for s in sources:
        if not s.get('enabled'): continue
        collector=COLLECTORS.get(s.get('type'))
        if not collector:
            print(f'Unknown source type: {s.get("type")}'); continue
        try: raw += collector({**s,'registry_path':str(ROOT/'config/sponsor_companies.yaml')})
        except Exception as e: print(f'Source failed: {s.get("id")}: {e}')
    new=[]
    for j in raw:
        x=score_job(j,p)
        if x['decision']=='SKIP' or not x.get('url'): continue
        if x['dedupe_key'] not in by:
            x['status']='new'; x['first_seen']=x['last_seen']; by[x['dedupe_key']]=x; new.append(x)
        else: by[x['dedupe_key']].update(x)
    jobs=sorted(by.values(),key=lambda x:x.get('match',{}).get('score',0),reverse=True)
    save_jobs(ROOT/'data/jobs.json',jobs); notify_new_jobs(new)
    return {'processed':len(raw),'new':len(new),'kept':len(jobs),'sources':len(sources)}
