import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; visa-job-radar/3.0)'}
JOB_PATH_HINT = re.compile(r'/jobs?/|/careers?/|jobid|job-details|position|requisition|opening|vacanc', re.I)


def _links(html, base, company, source_id, now):
    """Collect job-like links without applying candidate relevance filters."""
    soup = BeautifulSoup(html, 'html.parser')
    out, seen = [], set()
    for a in soup.select('a[href]'):
        title = ' '.join(a.get_text(' ', strip=True).split())
        href = urljoin(base, a.get('href', '')).split('#')[0]
        if not href.startswith('http') or len(title) < 5:
            continue
        if not JOB_PATH_HINT.search(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        parent = a.parent
        snippet = ' '.join(parent.parent.get_text(' ', strip=True).split()) if parent and parent.parent else title
        out.append({'company': company, 'title': title, 'location': '', 'url': href,
                     'description': snippet[:5000], 'source': source_id, 'last_seen': now})
    return out


def _candidate_urls(company):
    base = company['careers_url'].rstrip('/')
    name = company['name'].lower()
    urls = [base, base + '/jobs', base + '/careers', base + '/en/jobs', base + '/en-us/jobs']
    if name == 'amazon':
        urls = [
            'https://www.amazon.jobs/en/search?base_query=software+development+engineer&sort=recent&result_limit=100',
            'https://www.amazon.jobs/en/search?base_query=software+engineer&sort=recent&result_limit=100'
        ]
    elif name == 'google':
        urls = ['https://www.google.com/about/careers/applications/jobs/results/?q=software%20engineer']
    return list(dict.fromkeys(urls))


def collect(source):
    registry = source.get('registry_path')
    if not registry:
        raise ValueError('company_careers source requires registry_path')
    companies = json.load(open(registry, encoding='utf-8'))
    now = datetime.now(timezone.utc).isoformat()
    jobs, health = [], []

    for company in companies:
        company_jobs, errors = [], []
        urls = _candidate_urls(company)
        for url in urls:
            try:
                r = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
                r.raise_for_status()
                company_jobs.extend(_links(r.text, r.url, company['name'], source['id'], now))
            except Exception as exc:
                errors.append(f'{type(exc).__name__}: {str(exc)[:160]}')

        unique = {job['url']: job for job in company_jobs}
        company_jobs = list(unique.values())
        jobs.extend(company_jobs)
        health.append({
            'company': company['name'],
            'careers_url': company['careers_url'],
            'source_status': 'ok' if company_jobs else ('error' if errors else 'zero_results'),
            'urls_attempted': len(urls),
            'discovered': len(company_jobs),
            'errors': errors[:3]
        })

    print('CAREER_SOURCE_HEALTH ' + json.dumps(health, separators=(',', ':')))
    return {'jobs': jobs, 'health': health}
