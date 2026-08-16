import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

HEADERS={'User-Agent':'Mozilla/5.0 (compatible; visa-job-radar/2.0)'}
ROLE_HINTS=re.compile(r'backend|software engineer|software developer|developer|sde|api|platform|distributed|services|java|golang|go engineer|python engineer|node|full.?stack',re.I)
REJECT_HINTS=re.compile(r'engineering manager|software engineering manager|staff engineer|principal engineer|distinguished engineer|director|head of engineering|vp engineering|devops|site reliability|\bsre\b|security engineer|soc|data scientist|machine learning|\bml engineer\b|ai engineer|research scientist',re.I)
JOB_PATH_HINT=re.compile(r'/jobs?/|/careers?/|jobid|job-details|position|requisition',re.I)


def _links(html, base, company, source_id, now):
    soup=BeautifulSoup(html,'html.parser'); out=[]; seen=set()
    for a in soup.select('a[href]'):
        title=' '.join(a.get_text(' ',strip=True).split())
        href=urljoin(base,a.get('href','')).split('#')[0]
        if not href.startswith('http') or len(title)<8: continue
        if REJECT_HINTS.search(title) or not ROLE_HINTS.search(title): continue
        if not JOB_PATH_HINT.search(href): continue
        if href in seen: continue
        seen.add(href)
        parent=a.parent
        snippet=' '.join(parent.parent.get_text(' ',strip=True).split()) if parent and parent.parent else title
        out.append({'company':company,'title':title,'location':'','url':href,'description':snippet[:5000],'source':source_id,'last_seen':now})
    return out


def _candidate_urls(company):
    base=company['careers_url'].rstrip('/')
    name=company['name'].lower()
    urls=[base, base+'/jobs', base+'/careers', base+'/en/jobs', base+'/en-us/jobs']
    if name=='amazon':
        urls=['https://www.amazon.jobs/en/search?base_query=software+development+engineer&sort=recent&result_limit=100']
    elif name=='google':
        urls=['https://www.google.com/about/careers/applications/jobs/results/?q=software%20engineer']
    return list(dict.fromkeys(urls))


def collect(source):
    companies=json.load(open(source['registry_path'],encoding='utf-8'))
    now=datetime.now(timezone.utc).isoformat(); jobs=[]; health=[]
    for c in companies:
        found=0; status='ok'
        for url in _candidate_urls(c):
            try:
                r=requests.get(url,headers=HEADERS,timeout=25,allow_redirects=True); r.raise_for_status()
                batch=_links(r.text,r.url,c['name'],source['id'],now)
                jobs.extend(batch); found += len(batch)
            except Exception as e:
                status=f'error: {type(e).__name__}'
        health.append({'company':c['name'],'careers_url':c['careers_url'],'source_status':status,'discovered':found})
    print('CAREER_SOURCE_HEALTH '+json.dumps(health,separators=(',',':')))
    return jobs
