import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urlencode

COUNTRIES = {
    'AUS':'Australia','NZL':'New Zealand','ARE':'United Arab Emirates','DEU':'Germany',
    'GBR':'United Kingdom','IRL':'Ireland','CAN':'Canada','USA':'United States',
    'FRA':'France','NLD':'Netherlands','SWE':'Sweden','CHE':'Switzerland','DNK':'Denmark',
    'NOR':'Norway','FIN':'Finland','BEL':'Belgium','AUT':'Austria','ESP':'Spain',
    'PRT':'Portugal','ITA':'Italy','POL':'Poland','CZE':'Czech Republic','LUX':'Luxembourg'
}

HEADERS={'User-Agent':'Mozilla/5.0 (compatible; visa-job-radar/1.0)'}
JOB_RE=re.compile(r'/en/jobs/(\d+)/([^?#"<>]+)')

def collect(source):
    now=datetime.now(timezone.utc).isoformat()
    jobs=[]
    countries=source.get('countries', list(COUNTRIES))
    per_country=int(source.get('per_country',8))
    for code in countries:
        params={'base_query':'software development engineer','country':code,'sort':'recent','result_limit':per_country}
        url='https://www.amazon.jobs/en/search?'+urlencode(params)
        try:
            r=requests.get(url,headers=HEADERS,timeout=25)
            r.raise_for_status()
            soup=BeautifulSoup(r.text,'html.parser')
            seen=set()
            for a in soup.select('a[href*="/en/jobs/"]'):
                m=JOB_RE.search(a.get('href',''))
                title=' '.join(a.get_text(' ',strip=True).split())
                if not m or not title or len(title)<5:
                    continue
                job_id=m.group(1)
                if job_id in seen:
                    continue
                seen.add(job_id)
                href='https://www.amazon.jobs'+m.group(0)
                parent=a.parent
                snippet=' '.join(parent.parent.get_text(' ',strip=True).split()) if parent and parent.parent else title
                jobs.append({'company':'Amazon','title':title,'location':COUNTRIES.get(code,code),'url':href,'description':snippet,'source':source['id'],'last_seen':now})
                if len(seen)>=per_country:
                    break
        except Exception as e:
            print(f'Amazon source failed for {code}: {e}')
    return jobs
