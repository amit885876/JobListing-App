import re, hashlib
from datetime import datetime, timezone

def norm(s): return re.sub(r'[^a-z0-9+#]+',' ',(s or '').lower()).strip()
def hits(text, terms):
    n=norm(text); out=[]
    for x in terms:
        t=norm(x)
        if t and re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',n): out.append(x)
    return out

def experience(text):
    t=norm(text); m=re.search(r'(\d+)\s*(?:\+|or more)?\s*years?',t)
    if m:return {'value':int(m.group(1)),'confidence':'explicit'}
    if any(x in t for x in ['junior','graduate','entry level','early career']):return {'value':0,'confidence':'inferred'}
    if 'mid level' in t:return {'value':2,'confidence':'inferred'}
    if 'senior' in t:return {'value':4,'confidence':'inferred'}
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

BACKEND_SIGNALS=['backend','back end','server side','api','rest','graphql','grpc','microservice','service layer','web service','distributed system','database','data store','event driven','message queue','kafka','spring boot','node js','express js','scalable services','cloud native services']
PURE_PLATFORM=['devops','site reliability','sre','platform operations','cloud operations','infrastructure operations','security operations','soc']
PURE_AI=['machine learning','ml engineer','data scientist','ai engineer','ai research','research scientist','deep learning','computer vision','nlp engineer']
MANAGEMENT=['engineering manager','software engineering manager','engineering lead','people manager','director of engineering','head of engineering','vp engineering','staff engineer','staff software engineer','principal engineer','principal software engineer','distinguished engineer']
EXPLICIT_BACKEND_TITLE=['backend','back end','api engineer','distributed systems engineer','server side','application engineer']

def score_job(j,p):
    text=' '.join([j.get('company',''),j.get('title',''),j.get('location',''),j.get('description','')]); title=norm(j.get('title')); loc=norm(j.get('location'))
    if hits(title,p.get('excluded_roles',[])) or any(norm(x) in title for x in MANAGEMENT):
        return {**j,'dedupe_key':key(j),'decision':'SKIP','match':{'score':0,'confidence':1,'reasons':['Excluded role/seniority']}}
    backend_hits=hits(text,BACKEND_SIGNALS)
    title_backend=any(x in title for x in EXPLICIT_BACKEND_TITLE)
    if (any(x in title for x in PURE_PLATFORM) or any(x in title for x in PURE_AI)) and not backend_hits:
        return {**j,'dedupe_key':key(j),'decision':'SKIP','match':{'score':0,'confidence':1,'reasons':['Pure non-backend role']}}
    if not title_backend and not backend_hits:
        return {**j,'dedupe_key':key(j),'decision':'SKIP','match':{'score':0,'confidence':.95,'reasons':['No meaningful backend content']}}
    primary=hits(text,p['skills']['languages']+p['skills']['backend']); db=hits(text,p['skills']['databases']); dist=hits(text,p['skills']['distributed_data']); platform=hits(text,p['skills']['cloud_infra']+p['skills']['observability']); countries=hits(loc,p['target_regions']); exp=experience(text); vs=visa(text)
    s=25 if title_backend else 18; reasons=['Backend-focused role']
    if primary:s+=min(30,5*len(primary)); reasons.append('Skills: '+', '.join(primary[:7]))
    if db:s+=min(12,3*len(db)); reasons.append('Database match: '+', '.join(db[:4]))
    if dist:s+=min(12,3*len(dist)); reasons.append('Distributed/data match: '+', '.join(dist[:4]))
    if platform:s+=min(8,2*len(platform)); reasons.append('Cloud/infra supporting match')
    if countries:s+=8; reasons.append('Target location')
    if exp['value'] is None: reasons.append('Experience unknown; retained')
    elif exp['value']<=p['years_experience']+1:s+=8; reasons.append('Experience compatible')
    elif exp['value']>=p['years_experience']+3:s-=25; reasons.append('Likely too senior')
    else:s-=5; reasons.append('Slightly above target experience')
    if vs['status']=='explicit':s+=15; reasons.append('Explicit sponsorship')
    elif vs['status']=='likely':s+=8; reasons.append('Relocation/sponsorship signal')
    elif vs['status']=='no':s-=35; reasons.append('No sponsorship')
    else:reasons.append('Visa unknown; retained')
    s=max(0,min(100,s)); decision='APPLY' if s>=80 else 'REVIEW' if s>=65 else 'MAYBE' if s>=45 else 'LOW'
    confidence=.9 if j.get('description') and backend_hits else .78 if backend_hits else .70
    return {**j,'dedupe_key':key(j),'last_seen':datetime.now(timezone.utc).isoformat(),'experience':exp,'visa':vs,'match':{'score':s,'confidence':confidence,'reasons':reasons},'decision':decision}
