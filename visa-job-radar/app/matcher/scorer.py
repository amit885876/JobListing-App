import re, hashlib
from datetime import datetime, timezone

def norm(s): return re.sub(r'[^a-z0-9]+',' ',(s or '').lower()).strip()
def hits(text, terms):
    n=norm(text); return [x for x in terms if norm(x) in n]

def experience(text):
    t=norm(text); m=re.search(r'(\d+)\s*(?:\+|or more)?\s*years?',t)
    if m:return {'value':int(m.group(1)),'confidence':'explicit'}
    if any(x in t for x in ['junior','graduate','entry level','early career']):return {'value':0,'confidence':'inferred'}
    if 'mid level' in t or 'mid-level' in t:return {'value':2,'confidence':'inferred'}
    if any(x in t for x in ['senior']):return {'value':4,'confidence':'inferred'}
    if any(x in t for x in ['staff','principal','lead']):return {'value':6,'confidence':'inferred'}
    return {'value':None,'confidence':'unknown'}

def visa(text):
    t=norm(text)
    if any(x in t for x in ['visa sponsorship available','sponsorship available','will sponsor','visa sponsorship','work permit sponsorship','sponsor visa']):return {'status':'explicit','confidence':.95}
    if any(x in t for x in ['relocation assistance','relocation support','relocation package','relocation provided']):return {'status':'likely','confidence':.72}
    if any(x in t for x in ['no sponsorship','cannot sponsor','will not sponsor','must have existing work authorization']):return {'status':'no','confidence':.98}
    return {'status':'unknown','confidence':0}

def key(j):
    raw='|'.join([norm(j.get('company')),norm(j.get('title')),norm(j.get('location')),j.get('url','').split('?')[0]])
    return hashlib.sha256(raw.encode()).hexdigest()[:20]

BACKEND_SIGNALS=['backend','back end','server side','api','rest','graphql','grpc','microservice','service layer','web service','distributed system','database','data store','event driven','message queue','kafka','spring boot','node js','express js']
PURE_PLATFORM=['devops','site reliability','sre','platform operations','cloud operations','infrastructure operations','security operations','soc','machine learning','ml engineer','data scientist','research scientist','ai research']
MANAGEMENT=['engineering manager','software engineering manager','engineering lead','people manager','director of engineering','head of engineering','vp engineering','staff engineer','staff software engineer','principal engineer','principal software engineer','distinguished engineer']

def score_job(j,p):
    text=' '.join([j.get('company',''),j.get('title',''),j.get('location',''),j.get('description','')]); ntext=norm(text); title=norm(j.get('title')); loc=norm(j.get('location'))
    # Hard exclusions for roles the candidate explicitly does not want.
    if hits(title,p.get('excluded_roles',[])) or any(norm(x) in title for x in MANAGEMENT):
        return {**j,'dedupe_key':key(j),'decision':'SKIP','match':{'score':0,'confidence':1,'reasons':['Excluded seniority/management/platform role']}}
    backend_hits=[x for x in BACKEND_SIGNALS if norm(x) in ntext]
    platform_hits=[x for x in PURE_PLATFORM if norm(x) in title]
    # Require genuine backend content. Pure DevOps/SRE/AI/ML/security jobs are out unless their title/description also contains backend signals.
    title_backend=any(x in title for x in ['backend','back end','api engineer','software engineer','software development engineer','application engineer','member of technical staff'])
    pure_platform=bool(platform_hits) and not backend_hits
    pure_ai_ml=any(x in title for x in ['machine learning','ml engineer','data scientist','ai engineer','ai research','research scientist']) and not backend_hits
    if (pure_platform or pure_ai_ml) and not title_backend:
        return {**j,'dedupe_key':key(j),'decision':'SKIP','match':{'score':0,'confidence':1,'reasons':['Not backend-focused']}}
    if not backend_hits and not title_backend:
        return {**j,'dedupe_key':key(j),'decision':'SKIP','match':{'score':0,'confidence':.95,'reasons':['No meaningful backend content']}}

    roles=hits(title,p['target_roles']); primary=hits(text,p['skills']['languages']+p['skills']['backend']); db=hits(text,p['skills']['databases']); dist=hits(text,p['skills']['distributed_data']); platform=hits(text,p['skills']['cloud_infra']+p['skills']['observability']); countries=hits(loc,p['target_regions']); exp=experience(text); vs=visa(text)
    s=20 if title_backend else 12; reasons=['Backend-focused role']
    s+=min(30,5*len(primary));
    if primary: reasons.append('Skills: '+', '.join(primary[:6]))
    s+=min(12,3*len(db));
    if db: reasons.append('Database match: '+', '.join(db[:4]))
    s+=min(12,3*len(dist));
    if dist: reasons.append('Distributed/data match')
    s+=min(10,2*len(platform));
    if platform: reasons.append('Cloud/infra supporting match')
    if countries:s+=8;reasons.append('Target location')
    if exp['value'] is None:reasons.append('Experience unknown; retained')
    elif exp['value']<=p['years_experience']+1:s+=8;reasons.append('Experience compatible')
    elif exp['value']>=p['years_experience']+3:s-=25;reasons.append('Likely too senior')
    if vs['status']=='explicit':s+=15;reasons.append('Explicit sponsorship')
    elif vs['status']=='likely':s+=8;reasons.append('Relocation/sponsorship signal')
    elif vs['status']=='no':s-=35;reasons.append('No sponsorship')
    else:reasons.append('Visa unknown; retained')
    s=max(0,min(100,s)); decision='APPLY' if s>=80 else 'REVIEW' if s>=65 else 'MAYBE' if s>=45 else 'LOW'
    confidence=.85 if j.get('description') and backend_hits else .72 if backend_hits else .60
    return {**j,'dedupe_key':key(j),'last_seen':datetime.now(timezone.utc).isoformat(),'experience':exp,'visa':vs,'match':{'score':s,'confidence':confidence,'reasons':reasons},'decision':decision}
