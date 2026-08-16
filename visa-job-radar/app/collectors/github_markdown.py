import re, requests
from datetime import datetime, timezone

def collect(source):
    url=f"https://raw.githubusercontent.com/{source['owner']}/{source['repo']}/main/{source['path']}"
    r=requests.get(url,timeout=30,headers={'User-Agent':'visa-job-radar/0.1'})
    r.raise_for_status(); now=datetime.now(timezone.utc).isoformat(); jobs=[]
    for line in r.text.splitlines():
        if '|' not in line: continue
        cells=[x.strip() for x in line.strip().strip('|').split('|')]
        if len(cells)<3 or ('company' in cells[0].lower() and 'job' in cells[1].lower()): continue
        company,title,location=cells[:3]; link=''
        if len(cells)>3:
            m=re.search(r'https?://[^\\s)]+',cells[3])
            if m: link=m.group(0).rstrip('.,')
        if company and title and location:
            jobs.append({'company':company,'title':title,'location':location,'url':link,'source':source['id'],'last_seen':now})
    return jobs
