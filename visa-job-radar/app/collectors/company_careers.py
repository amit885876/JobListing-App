import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126 Safari/537.36 visa-job-radar/4.0'
}
TIMEOUT = 25
MAX_PAGES = 12
JOB_PATH_HINT = re.compile(
    r'(?:/jobs?/|/careers?/|jobid|job-details|job-detail|position|requisition|opening|vacanc|/apply)',
    re.I,
)
JOB_TITLE_HINT = re.compile(
    r'\b(software|backend|developer|engineer|engineering|developer|development|sde|programmer|technical|data|product|devops|sre|security|scientist|designer)\b',
    re.I,
)


def _get(url):
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


def _normalize_url(url):
    return url.split('#')[0].rstrip('/')


def _job_from_jsonld(obj, company, source_id, now, page_url):
    if isinstance(obj, list):
        for item in obj:
            result = _job_from_jsonld(item, company, source_id, now, page_url)
            if result:
                yield result
        return
    if not isinstance(obj, dict):
        return
    if obj.get('@type') != 'JobPosting':
        if isinstance(obj.get('@graph'), list):
            for item in obj['@graph']:
                yield from _job_from_jsonld(item, company, source_id, now, page_url)
        return

    location = obj.get('jobLocation') or obj.get('jobLocationType') or ''
    if isinstance(location, list):
        location = ', '.join(
            str((x.get('address') or {}).get('addressLocality') or x.get('name') or '')
            for x in location if isinstance(x, dict)
        )
    elif isinstance(location, dict):
        address = location.get('address') or {}
        location = ', '.join(str(x) for x in [
            address.get('addressLocality'), address.get('addressRegion'), address.get('addressCountry')
        ] if x)
    url = obj.get('url') or page_url
    yield {
        'company': company,
        'title': str(obj.get('title') or '').strip(),
        'location': str(location).strip(),
        'url': _normalize_url(url),
        'description': BeautifulSoup(str(obj.get('description') or ''), 'html.parser').get_text(' ', strip=True)[:12000],
        'source': source_id,
        'last_seen': now,
    }


def _extract_jobs(html, base_url, company, source_id, now):
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []

    # First preference: structured JobPosting data. This is much stronger evidence
    # than treating every /careers/ link as a job.
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
            jobs.extend(_job_from_jsonld(data, company, source_id, now, base_url))
        except Exception:
            continue

    seen = {j['url'] for j in jobs if j.get('url')}
    for a in soup.select('a[href]'):
        title = ' '.join(a.get_text(' ', strip=True).split())
        href = _normalize_url(urljoin(base_url, a.get('href', '')))
        if not href.startswith(('http://', 'https://')) or len(title) < 8:
            continue
        if href in seen or not JOB_PATH_HINT.search(href):
            continue
        if not JOB_TITLE_HINT.search(title):
            continue
        # Avoid collecting navigation/company pages as jobs.
        path = urlparse(href).path.lower()
        if path.rstrip('/') in {'/jobs', '/careers', '/career', '/openings'}:
            continue
        parent = a.parent
        snippet = ' '.join(parent.parent.get_text(' ', strip=True).split()) if parent and parent.parent else title
        jobs.append({
            'company': company,
            'title': title,
            'location': '',
            'url': href,
            'description': snippet[:12000],
            'source': source_id,
            'last_seen': now,
        })
        seen.add(href)
    return jobs


def _greenhouse(company, source_id, now, careers_url):
    parsed = urlparse(careers_url)
    parts = [p for p in parsed.path.split('/') if p]
    slug = parts[-1] if parts else ''
    if 'greenhouse.io' not in parsed.netloc or not slug:
        return []
    url = f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true'
    data = _get(url).json()
    return [{
        'company': company,
        'title': j.get('title', '').strip(),
        'location': ((j.get('location') or {}).get('name') or '').strip(),
        'url': j.get('absolute_url', '').strip(),
        'description': BeautifulSoup(j.get('content', ''), 'html.parser').get_text(' ', strip=True)[:12000],
        'source': source_id,
        'last_seen': now,
    } for j in data.get('jobs', []) if j.get('absolute_url')]


def _lever(company, source_id, now, careers_url):
    parsed = urlparse(careers_url)
    if 'jobs.lever.co' not in parsed.netloc:
        return []
    slug = next((p for p in parsed.path.split('/') if p), '')
    if not slug:
        return []
    data = _get(f'https://api.lever.co/v0/postings/{slug}?mode=json').json()
    jobs = []
    for j in data if isinstance(data, list) else []:
        jobs.append({
            'company': company,
            'title': (j.get('text') or '').strip(),
            'location': ((j.get('categories') or {}).get('location') or '').strip(),
            'url': (j.get('hostedUrl') or j.get('applyUrl') or '').strip(),
            'description': BeautifulSoup((j.get('descriptionPlain') or j.get('description') or ''), 'html.parser').get_text(' ', strip=True)[:12000],
            'source': source_id,
            'last_seen': now,
        })
    return [j for j in jobs if j['url']]


def _candidate_urls(company):
    base = company['careers_url'].rstrip('/')
    name = company['name'].lower()
    if name == 'amazon':
        return [
            'https://www.amazon.jobs/en/search?base_query=software+development+engineer&sort=recent&result_limit=100',
            'https://www.amazon.jobs/en/search?base_query=software+engineer&sort=recent&result_limit=100',
        ]
    if name == 'google':
        return [
            'https://www.google.com/about/careers/applications/jobs/results/?q=software%20engineer',
            'https://www.google.com/about/careers/applications/jobs/results/?q=software%20developer',
        ]
    if name == 'microsoft':
        return [
            'https://jobs.careers.microsoft.com/global/en/search?q=software%20engineer',
            'https://jobs.careers.microsoft.com/global/en/search?q=software%20development%20engineer',
        ]
    return list(dict.fromkeys([base, base + '/jobs', base + '/careers', base + '/en/jobs', base + '/en-us/jobs']))


def _paginate_links(first_url, html, max_pages=MAX_PAGES):
    soup = BeautifulSoup(html, 'html.parser')
    urls = [first_url]
    for a in soup.select('a[href]'):
        text = ' '.join(a.get_text(' ', strip=True).split()).lower()
        rel = ' '.join(a.get('rel', [])).lower()
        if text in {'next', 'next page', 'older', 'load more'} or 'next' in rel:
            nxt = _normalize_url(urljoin(first_url, a['href']))
            if nxt not in urls:
                urls.append(nxt)
        if len(urls) >= max_pages:
            break
    return urls


def collect(source):
    registry = source.get('registry_path')
    if not registry:
        raise ValueError('company_careers source requires registry_path')
    with open(registry, encoding='utf-8') as fh:
        companies = json.load(fh)

    now = datetime.now(timezone.utc).isoformat()
    all_jobs, health = [], []

    for company in companies:
        name = company['name']
        company_jobs, errors = [], []
        attempted = []
        try:
            direct = _greenhouse(name, source['id'], now, company['careers_url'])
            if not direct:
                direct = _lever(name, source['id'], now, company['careers_url'])
            if direct:
                company_jobs.extend(direct)
                attempted.append('ats-api')
            else:
                attempted.append('html')
                for url in _candidate_urls(company):
                    try:
                        response = _get(url)
                        pages = _paginate_links(response.url, response.text)
                        for page_url in pages:
                            try:
                                page = response.text if page_url == response.url else _get(page_url).text
                                company_jobs.extend(_extract_jobs(page, page_url, name, source['id'], now))
                            except Exception as exc:
                                errors.append(f'{type(exc).__name__}: {str(exc)[:180]}')
                    except Exception as exc:
                        errors.append(f'{type(exc).__name__}: {str(exc)[:180]}')
                    attempted.append(url)
        except Exception as exc:
            errors.append(f'{type(exc).__name__}: {str(exc)[:180]}')

        unique = {}
        for job in company_jobs:
            url = job.get('url')
            if url:
                unique[url] = job
        company_jobs = list(unique.values())
        all_jobs.extend(company_jobs)

        if company_jobs:
            status = 'ok'
        elif errors:
            status = 'failed'
        else:
            status = 'no_jobs_found'

        health.append({
            'company': name,
            'careers_url': company['careers_url'],
            'status': status,
            'crawler_verified': bool(company_jobs),
            'discovered': len(company_jobs),
            'urls_attempted': len(attempted),
            'errors': errors[:5],
            'checked_at': now,
        })

    print('CAREER_SOURCE_HEALTH ' + json.dumps(health, separators=(',', ':')))
    return {'jobs': all_jobs, 'health': health}
