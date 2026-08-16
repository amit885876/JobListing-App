import json
from pathlib import Path

def load_jobs(path):
    if not Path(path).exists(): return []
    try: return json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception: return []

def save_jobs(path, jobs):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding='utf-8')
