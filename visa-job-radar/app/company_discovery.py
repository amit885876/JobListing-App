"""Company-universe discovery and career-source resolution.

The persisted companies.json is the source of truth for job crawling. This module
keeps discovery separate from job collection so a missing job feed never silently
removes a sponsor company from the monitor.
"""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
COMPANIES = ROOT / "data" / "companies.json"
TARGET = {"AU","NZ","AE","DE","GB","IE","CA","US","FR","NL","BE","CH","SE","DK","NO","FI","AT","ES","IT","PL","CZ","LU"}


def load_companies() -> list[dict]:
    with COMPANIES.open(encoding="utf-8") as f:
        companies = json.load(f)
    seen = set(); out = []
    for c in companies:
        name = c["name"].strip()
        key = name.casefold()
        countries = sorted(set(c.get("countries", [])) & TARGET)
        if not name or key in seen or not countries:
            continue
        seen.add(key)
        out.append({**c, "name": name, "countries": countries})
    return out


def source_type(career_url: str) -> str:
    host = urlparse(career_url).netloc.lower()
    if "amazon.jobs" in host: return "amazon"
    if "workday" in host: return "workday"
    if "greenhouse" in host: return "greenhouse"
    if "lever" in host: return "lever"
    if "ashby" in host: return "ashby"
    if "smartrecruiters" in host: return "smartrecruiters"
    return "company_generic"


def build_source_manifest() -> list[dict]:
    return [{**c, "source_type": source_type(c["careers_url"])} for c in load_companies()]


if __name__ == "__main__":
    manifest = build_source_manifest()
    print(f"companies={len(manifest)}")
    for c in manifest:
        print(f"{c['name']} | {c['source_type']} | {','.join(c['countries'])}")
