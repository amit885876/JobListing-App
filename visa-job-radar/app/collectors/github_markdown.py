import re, requests
from datetime import datetime, timezone

URL_RE = re.compile(r'https?://[^\s)\]>]+')
MD_LINK_RE = re.compile(r'\[[^\]]*\]\((https?://[^)]+)\)')

def clean_md(value):
    value=re.sub(r'!\[[^\]]*\]\([^)]*\)','',value or '')
    value=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',value)
    return re.sub(r'[*_`#]','',value).strip()

def extract_link(cells):
    for cell in cells[3:]:
        m=MD_LINK_RE.search(cell) or URL_RE.search(cell)
        if m:return (m.group(1) if m.lastindex else m.group(0)).rstrip('.,')
    return ''

def collect(source):
    url=f"https://raw.githubusercontent.com/{source['owner']}/{source['repo']}/main/{source['path']}"
    r=requests.get(url,timeout=30,headers={'User-Agent':'visa-job-radar/1.0'}); r.raise_for_status()
    now=datetime.now(timezone.utc).isoformat(); jobs=[]
    for line in r.text.splitlines():
        if '|' not in line: continue
        cells=[x.strip() for x in line.strip().strip('|').split('|')]
        if len(cells)<3: continue
        header=' '.join(c.lower() for c in cells[:4])
        if 'company' in header and ('job' in header or 'role' in header or 'title' in header): continue
        company,title,location=map(clean_md,cells[:3])
        if not company or not title or not location: continue
        link=extract_link(cells)
        jobs.append({'company':company,'title':title,'location':location,'url':link,'source':source['id'],'last_seen':now})
    return jobs
