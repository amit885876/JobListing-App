import re
import requests
import yaml
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin

HEADERS={'User-Agent':'Mozilla/5.0 (compatible; visa-job-radar/1.0)'}
ROLE_HINTS=re.compile(r'backend|software engineer|software developer|developer|sde|api|platform|distributed|services|java|golang|go engineer|python engineer|node|full.?stack',re.I)
REJECT_HINTS=re.compile(r'engineering manager|software engineering manager|staff engineer|principal engineer|distinguished engineer|director|head of engineering|vp engineering|devops|site reliability|\bsre\b|security engineer|soc|data scientist|machine learning|\bml engineer\b|ai engineer|research scientist',re.I)
JOB_HOSTS=('greenhouse.io','lever.co','ashbyhq.com','myworkdayjobs.com','smartrecruiters.com')

def _links(html, base, company, source_id, now):
    soup=BeautifulSoup(html,'html.parser'); out=[]; seen=set()
    for a in soup.select('a[href]'):
        title=' '.join(a.get_text(' ',strip=True).split())
        href=urljoin(base,a.get('href',''))
        if not href.startswith('http') or len(title)<8: continue
        if REJECT_HINTS.search(title) or not ROLE_HINTS.search(title): continue
        host=href.lower()
        looks_job=any(x in host for x in JOB_HOSTS) or re.search(r'/jobs?/|/careers?/|jobid|job-details|position',href,re.I)
        if not looks_job: continue
        key=href.split('#')[0].rstrip('/')
        if key in seen: continue
        seen.add(key)
        parent=a.parent
        snippet=' '.join(parent.parent.get_text(' ',strip=True).split()) if parent and parent.parent else title
        out.append({'company':company,'title':title,'location':'','url':key,'description':snippet[:2500],'source':source_id,'last_seen':now})
    return out

def collect(source):
    registry=yaml.safe_load(open(source['registry_path']))['companies']
    now=datetime.now(timezone.utc).isoformat(); jobs=[]
    for c in registry:
        url=c.get('careers_url');
        if not url: continue
        try:
            r=requests.get(url,headers=HEADERS,timeout=25,allow_redirects=True); r.raise_for_status()
            jobs.extend(_links(r.text,r.url,c['name'],source['id'],now))
        except Exception as e:
            print(f'Career page failed for {c.get("name")}: {e}')
    return jobs
