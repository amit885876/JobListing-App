import os,requests

def notify_new_jobs(jobs,min_score=80):
    token=os.getenv('TELEGRAM_BOT_TOKEN'); chat=os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat:return
    for j in [x for x in jobs if x.get('match',{}).get('score',0)>=min_score][:10]:
        m=j['match']; text=f"🔥 {m['score']}/100 — {j['title']}\\n{j['company']} · {j['location']}\\nVisa: {j.get('visa',{}).get('status')}\\n{j.get('url','')}"
        requests.post(f'https://api.telegram.org/bot{token}/sendMessage',json={'chat_id':chat,'text':text},timeout=15)
