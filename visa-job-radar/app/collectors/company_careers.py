import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/126 Safari/537.36 visa-job-radar/5.0',
    'Accept-Language': 'en-US,en;q=0.9',
}
TIMEOUT = 30
MAX_PAGES = 30
AMAZON_PAGE_SIZE = 100
GOOGLE_QUERIES = ('software engineer', 'software development engineer', 'backend engineer')
MICROSOFT_QUERIES = ('software engineer', 'software development engineer', 'backend engineer')


def _get(url, params=None, accept=None):
    headers = dict(HEADERS)
    if accept:
        headers['Accept'] = accept
    response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response


def _normalize_url(url):
    return (url or '').split('#')[0].rstrip('/')


def _text(value):
    return ' '.join(str(value or '').split())


def _job(company, title, location, url, description, source_id, now):
    return {
        'company': company,
        'title': _text(title),
        'location': _text(location),
        'url': _normalize_url(url),
        'description': _text(description)[:16000],
        'source': source_id,
        'last_seen': now,
    }


def _job_from_jsonld(obj, company, source_id, now, page_url):
    if isinstance(obj, list):
        for item in obj:
            yield from _job_from_jsonld(item, company, source_id, now, page_url)
        return
    if not isinstance(obj, dict):
        return
    if obj.get('@type') == 'JobPosting':
        location = obj.get('jobLocation') or obj.get('jobLocationType') or ''
        if isinstance(location, list):
            values = []
            for item in location:
                if isinstance(item, dict):
                    address = item.get('address') or {}
                    values.append(_text(address.get('addressLocality') or item.get('name') or ''))
            location = ', '.join(x for x in values if x)
        elif isinstance(location, dict):
            address = location.get('address') or {}
            location = ', '.join(x for x in (
                address.get('addressLocality'), address.get('addressRegion'), address.get('addressCountry')
            ) if x)
        description = BeautifulSoup(str(obj.get('description') or ''), 'html.parser').get_text(' ', strip=True)
        yield _job(company, obj.get('title'), location, obj.get('url') or page_url,
                   description, source_id, now)
    for child in obj.get('@graph', []) if isinstance(obj.get('@graph'), list) else []:
        yield from _job_from_jsonld(child, company, source_id, now, page_url)


def _extract_jsonld(html, page_url, company, source_id, now):
    soup = BeautifulSoup(html, 'html.parser')
    jobs = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
            jobs.extend(_job_from_jsonld(data, company, source_id, now, page_url))
        except Exception:
            continue
    return jobs


def _extract_job_links(html, base_url, company, source_id, now):
    soup = BeautifulSoup(html, 'html.parser')
    jobs = _extract_jsonld(html, base_url, company, source_id, now)
    seen = {j['url'] for j in jobs if j.get('url')}
    job_url = re.compile(r'(?:/jobs?/|/careers?/[^?#]+/|/job/|/positions?/|/vacanc|/opening|/requisition|jobid=)', re.I)
    title_hint = re.compile(r'\b(software|backend|developer|engineer|engineering|development|sde|programmer|technical)\b', re.I)
    for a in soup.select('a[href]'):
        title = _text(a.get_text(' ', strip=True))
        href = _normalize_url(urljoin(base_url, a.get('href', '')))
        if len(title) < 8 or not href.startswith(('http://', 'https://')):
            continue
        if href in seen or not title_hint.search(title) or not job_url.search(href):
            continue
        path = urlparse(href).path.lower().rstrip('/')
        if path in {'/jobs', '/careers', '/career', '/openings'}:
            continue
        parent = a.parent
        snippet = _text(parent.parent.get_text(' ', strip=True) if parent and parent.parent else title)
        jobs.append(_job(company, title, '', href, snippet, source_id, now))
        seen.add(href)
    return jobs


def _greenhouse(company, source_id, now, careers_url):
    parsed = urlparse(careers_url)
    if 'greenhouse.io' not in parsed.netloc:
        return []
    parts = [p for p in parsed.path.split('/') if p]
    slug = parts[-1] if parts else ''
    if not slug:
        return []
    data = _get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs', {'content': 'true'}, 'application/json').json()
    return [_job(company, j.get('title'), (j.get('location') or {}).get('name'), j.get('absolute_url'),
                  BeautifulSoup(j.get('content', ''), 'html.parser').get_text(' ', strip=True), source_id, now)
            for j in data.get('jobs', []) if j.get('absolute_url')]


def _lever(company, source_id, now, careers_url):
    parsed = urlparse(careers_url)
    if 'jobs.lever.co' not in parsed.netloc:
        return []
    slug = next((p for p in parsed.path.split('/') if p), '')
    if not slug:
        return []
    data = _get(f'https://api.lever.co/v0/postings/{slug}', {'mode': 'json'}, 'application/json').json()
    return [_job(company, j.get('text'), (j.get('categories') or {}).get('location'),
                  j.get('hostedUrl') or j.get('applyUrl'), j.get('descriptionPlain') or j.get('description'), source_id, now)
            for j in data if isinstance(j, dict) and (j.get('hostedUrl') or j.get('applyUrl'))]


def _amazon(company, source_id, now):
    jobs = []
    offset = 0
    while offset < 5000:
        params = {
            'offset': offset,
            'result_limit': AMAZON_PAGE_SIZE,
            'sort': 'recent',
            'base_query': 'software engineer',
        }
        data = _get('https://www.amazon.jobs/en/search.json', params, 'application/json').json()
        page = data.get('jobs') or []
        if not page:
            break
        for j in page:
            path = j.get('job_path') or j.get('job_url')
            url = path if str(path).startswith('http') else urljoin('https://www.amazon.jobs', str(path or ''))
            jobs.append(_job(company, j.get('title'), j.get('location'), url,
                             j.get('description') or j.get('basic_qualifications') or '', source_id, now))
        offset += len(page)
        total = int(data.get('hits') or 0)
        if total and offset >= total:
            break
        if len(page) < AMAZON_PAGE_SIZE:
            break
    return jobs


def _google(company, source_id, now):
    jobs = []
    seen = set()
    for query in GOOGLE_QUERIES:
        for page in range(1, MAX_PAGES + 1):
            url = 'https://www.google.com/about/careers/applications/jobs/results'
            response = _get(url, {'q': query, 'page': page})
            soup = BeautifulSoup(response.text, 'html.parser')
            found = []
            for a in soup.select('a[href*="/about/careers/applications/jobs/"]'):
                href = _normalize_url(urljoin(response.url, a.get('href')))
                title = _text(a.get_text(' ', strip=True))
                if '/jobs/' not in href or len(title) < 8 or href in seen:
                    continue
                # Google result cards contain the title and nearby location/team text.
                card = a.parent.parent if a.parent else a
                snippet = _text(card.get_text(' ', strip=True))
                jobs.append(_job(company, title, '', href, snippet, source_id, now))
                seen.add(href)
                found.append(href)
            if not found:
                break
    return jobs


def _microsoft(company, source_id, now):
    jobs = []
    seen = set()
    for query in MICROSOFT_QUERIES:
        for page in range(1, MAX_PAGES + 1):
            url = 'https://jobs.careers.microsoft.com/global/en/search'
            response = _get(url, {'q': query, 'pg': page, 'pgSz': 50})
            found = _extract_job_links(response.text, response.url, company, source_id, now)
            fresh = [j for j in found if j.get('url') and j['url'] not in seen]
            if not fresh:
                break
            for j in fresh:
                seen.add(j['url'])
            jobs.extend(fresh)
    return jobs


def _company_jobs(company, source_id, now):
    name = company['name'].strip().lower()
    url = company['careers_url']
    # Dedicated sources are tried first; generic HTML is the fallback, never the primary strategy.
    if name == 'amazon':
        return _amazon(company['name'], source_id, now), ['amazon-search.json']
    if name == 'google':
        return _google(company['name'], source_id, now), ['google-careers-results']
    if name == 'microsoft':
        return _microsoft(company['name'], source_id, now), ['microsoft-careers-search']
    if 'greenhouse.io' in urlparse(url).netloc:
        return _greenhouse(company['name'], source_id, now, url), ['greenhouse-api']
    if 'jobs.lever.co' in urlparse(url).netloc:
        return _lever(company['name'], source_id, now, url), ['lever-api']

    # For every other company, crawl the actual supplied career page and discover
    # real JobPosting JSON-LD or job-detail links. We never treat the homepage itself as a job.
    response = _get(url)
    jobs = _extract_job_links(response.text, response.url, company['name'], source_id, now)
    return jobs, [response.url]


def collect(source):
    registry = source.get('registry_path')
    if not registry:
        raise ValueError('company_careers source requires registry_path')
    with open(registry, encoding='utf-8') as fh:
        companies = json.load(fh)

    now = datetime.now(timezone.utc).isoformat()
    all_jobs = []
    health = []

    # Company-by-company isolation: a broken company can never stop the rest.
    # The health record is written for EVERY company, whether it succeeds or fails.
    for company in companies:
        name = company['name']
        errors = []
        attempts = []
        try:
            jobs, attempts = _company_jobs(company, source['id'], now)
        except Exception as exc:
            jobs = []
            errors.append(f'{type(exc).__name__}: {str(exc)[:300]}')

        unique = {}
        for job in jobs:
            if job.get('url'):
                unique[job['url']] = job
        jobs = list(unique.values())
        all_jobs.extend(jobs)

        if jobs:
            status = 'ok'
        elif errors:
            status = 'failed'
        else:
            status = 'zero_results'

        health.append({
            'company': name,
            'careers_url': company['careers_url'],
            'status': status,
            'crawler_verified': bool(jobs),
            'discovered': len(jobs),
            'urls_attempted': len(attempts),
            'attempts': attempts,
            'errors': errors[:5],
            'checked_at': now,
        })

        print(f'[CRAWLER] {name}: {status} ({len(jobs)} jobs)')

    print('CAREER_SOURCE_HEALTH ' + json.dumps(health, separators=(',', ':')))
    return {'jobs': all_jobs, 'health': health}
