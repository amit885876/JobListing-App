import re, hashlib
from datetime import datetime, timezone

def norm(s): return re.sub(r'[^a-z0-9]+',' ',(s or '').lower()).strip()
def hits(text, terms): return [x for x in terms if norm(x) in norm(text)]

def experience(text):
    t=norm(text); m=re.search(r'(\d+)\s*(?:\+|or more)?\s*years?',t)
    if m:return {'value':int(m.group(1)),'confidence':'explicit'}
    if any(x in t for x in ['junior','graduate','entry level','early career']):return {'value':0,'confidence':'inferred'}
    if 'mid level' in t or 'mid-level' in t:return {'value':2,'confidence':'inferred'}
    if any(x in t for x in ['senior','staff','principal','lead']):return {'value':5,'confidence':'inferred'}
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

def score_job(j,p):
    text=' '.join([j.get('company',''),j.get('title',''),j.get('location',''),j.get('description','')]); title=norm(j.get('title')); loc=norm(j.get('location'))
    if hits(title,p['excluded_roles']): return {**j,'dedupe_key':key(j),'decision':'SKIP','match':{'score':0,'confidence':1,'reasons':['Excluded role']}}
    roles=hits(title,p['target_roles']); primary=hits(text,p['skills']['languages']+p['skills']['backend']); platform=hits(text,p['skills']['cloud_infra']+p['skills']['observability']); dist=hits(text,p['skills']['distributed_data']); countries=hits(loc,p['target_regions']); exp=experience(text); vs=visa(text)
    s=0; reasons=[]
    if roles:s+=25;reasons.append('Target engineering role')
    if primary:s+=min(35,7*len(primary));reasons.append('Technical skills: '+', '.join(primary))
    if platform:s+=min(15,5*len(platform));reasons.append('Cloud/platform match')
    if dist:s+=min(12,4*len(dist));reasons.append('Distributed/data match')
    if countries:s+=10;reasons.append('Target location')
    if exp['value'] is None:reasons.append('Experience not stated; retained')
    elif exp['value']<=p['years_experience']+1:s+=8;reasons.append('Experience compatible')
    elif exp['value']>=p['years_experience']+3:s-=15;reasons.append('Likely too senior')
    if vs['status']=='explicit':s+=15;reasons.append('Explicit sponsorship')
    elif vs['status']=='likely':s+=8;reasons.append('Relocation/sponsorship signal')
    elif vs['status']=='no':s-=35;reasons.append('No sponsorship')
    else:reasons.append('Visa unknown; retained')
    s=max(0,min(100,s)); decision='APPLY' if s>=80 else 'REVIEW' if s>=65 else 'MAYBE' if s>=35 else 'LOW'
    confidence=.80 if j.get('description') and primary else .70 if primary else .55
    return {**j,'dedupe_key':key(j),'last_seen':datetime.now(timezone.utc).isoformat(),'experience':exp,'visa':vs,'match':{'score':s,'confidence':confidence,'reasons':reasons},'decision':decision}
