#!/usr/bin/env python3
"""Revenue-priority ops loop for Hermes dashboard.

Prioritizes money-intent WP drafts from revised/, promotes them to reviewed/ via
existing QA repair, optionally publishes a bounded number, and writes a concise
machine-readable report.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path('/Volumes/WorkDrive/Develop/48.HermesAgent/dashboard')
REVISED = BASE / 'drafts/revised'
REVIEWED = BASE / 'drafts/reviewed'
PUBLISHED = BASE / 'drafts/published'
DATA = BASE / 'data'
RESCUE_SCRIPT = BASE / 'scripts/rescue_wp_revised_to_reviewed.py'
PUBLISH_SCRIPT = BASE / 'scripts/cron/publish-blogs.sh'

MONEY_TERMS: dict[str, int] = {
    '대출': 10, '금리': 9, '전세대출': 10, '디딤돌': 9, '버팀목': 9, '대환': 8,
    '보험': 9, '실손': 10, '자동차보험': 10, '여행자보험': 8, '암보험': 9, '보험금': 8,
    '지원금': 9, '소상공인': 9, '청년': 6, '창업': 7, '폐업': 8, '점포철거': 10,
    '세액공제': 10, '연말정산': 10, '연금저축': 9, 'IRP': 9, 'ISA': 9,
    '영양제': 8, '단백질': 7, '오메가': 7, '마그네슘': 7, '혈당': 8, '다이어트': 7,
}

SITE_CAP = {'unpre': 3, 'untab': 2, 'skewese': 2}


def load_rescue_module():
    spec = importlib.util.spec_from_file_location('rescue_wp_revised_to_reviewed', RESCUE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load {RESCUE_SCRIPT}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def site_from_name(path: Path) -> str:
    m = re.search(r'_wp-([^_]+)_', path.name)
    return m.group(1) if m else ''


def frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith('---'):
        return '', text
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        return '', text
    return m.group(1), text[m.end():]


def read_field(text: str, key: str) -> str:
    fm, _ = frontmatter(text)
    m = re.search(rf'^{re.escape(key)}:\s*["\']?([^"\'\n]+)', fm, re.M)
    return m.group(1).strip() if m else ''


def set_field(text: str, key: str, value: str) -> str:
    fm, body = frontmatter(text)
    if not fm:
        return text
    line = f'{key}: "{value}"'
    if re.search(rf'^{re.escape(key)}:', fm, re.M):
        fm = re.sub(rf'^{re.escape(key)}:.*$', line, fm, flags=re.M)
    else:
        fm = fm.rstrip() + '\n' + line
    return f'---\n{fm}\n---\n{body}'


def desired_offer(site: str, haystack: str) -> str:
    h = haystack.lower()
    if site == 'unpre':
        head = h[:500]
        loan_terms = ['대출', '금리', '전세', '디딤돌', '버팀목', '대환', '월세']
        tax_terms = ['세액공제', '연말정산', '연금저축', 'irp', 'isa', '저축계좌', '내일저축']
        if any(k.lower() in head for k in tax_terms):
            return 'unpre_tax_saving_check'
        if any(k in head for k in loan_terms):
            return 'unpre_loan_rate_check'
        if any(k in h for k in loan_terms):
            return 'unpre_loan_rate_check'
        if any(k.lower() in h for k in tax_terms):
            return 'unpre_tax_saving_check'
        return 'unpre_insurance_quote'
    if site == 'untab':
        if any(k in h for k in ['지원금', '소상공인', '창업', '폐업', '점포철거', '정책']):
            return 'untab_policy_fund_consult'
        return 'untab_subsidy_eligibility'
    if site == 'skewese':
        return 'skewese_supplement_buying_check'
    return ''


def score_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding='utf-8', errors='ignore')
    site = site_from_name(path)
    title = read_field(text, 'title') or read_field(text, 'topic') or path.stem
    haystack = f'{path.name}\n{title}\n{text[:12000]}'
    score = 0
    hits: dict[str, int] = {}
    lower = haystack.lower()
    for term, weight in MONEY_TERMS.items():
        cnt = lower.count(term.lower())
        if cnt:
            hits[term] = cnt
            score += min(cnt, 8) * weight
    offer = read_field(text, 'offer_id')
    want = desired_offer(site, haystack)
    if offer == want and offer:
        score += 20
    elif offer and want and offer != want:
        score -= 10
    if site in SITE_CAP:
        score += 10
    return {'path': path, 'file': path.name, 'site': site, 'title': title, 'score': score, 'offer': offer, 'desired_offer': want, 'hits': hits}


def fix_offer_if_needed(path: Path, desired: str, dry_run: bool) -> bool:
    if not desired:
        return False
    text = path.read_text(encoding='utf-8', errors='ignore')
    current = read_field(text, 'offer_id')
    if current == desired:
        return False
    updated = set_field(text, 'offer_id', desired)
    if updated != text and not dry_run:
        path.write_text(updated, encoding='utf-8')
    return updated != text


def select_candidates(limit: int) -> list[dict[str, Any]]:
    rows = [score_file(p) for p in REVISED.glob('*_wp-*.md')]
    rows = [r for r in rows if r['score'] > 0 and r['site'] in SITE_CAP]
    rows.sort(key=lambda r: (r['score'], r['site'], r['file']), reverse=True)
    selected: list[dict[str, Any]] = []
    per_site: dict[str, int] = {}
    for row in rows:
        site = row['site']
        if per_site.get(site, 0) >= SITE_CAP[site]:
            continue
        selected.append(row)
        per_site[site] = per_site.get(site, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def run_publish(site: str) -> dict[str, Any]:
    env = os.environ.copy()
    env['HERMES_SITE'] = site
    env['HERMES_WP_STATUS'] = 'publish'
    proc = subprocess.run(
        ['bash', str(PUBLISH_SCRIPT)],
        cwd=str(BASE),
        env=env,
        text=True,
        capture_output=True,
        timeout=420,
    )
    out = (proc.stdout or '') + (proc.stderr or '')
    m = re.search(r'https://[^\s"]+', out)
    return {'site': site, 'returncode': proc.returncode, 'success': '"success": true' in out, 'url': m.group(0) if m else '', 'tail': out[-2000:]}


def count_state() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for state in ['reviewed', 'revised', 'published']:
        d = BASE / 'drafts' / state
        counts = {'wp': 0, 'shorts': 0, 'longform': 0, 'other': 0}
        for p in d.glob('*.md'):
            n = p.name
            if '_wp-' in n:
                counts['wp'] += 1
            elif '-shorts_' in n:
                counts['shorts'] += 1
            elif '-longform_' in n:
                counts['longform'] += 1
            else:
                counts['other'] += 1
        result[state] = counts
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--promote-limit', type=int, default=5)
    ap.add_argument('--publish-wp-limit', type=int, default=3)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    started = datetime.now().isoformat(timespec='seconds')
    before = count_state()
    selected = select_candidates(args.promote_limit)
    report: dict[str, Any] = {
        'started_at': started,
        'dry_run': args.dry_run,
        'selected': [{k: v for k, v in r.items() if k != 'path'} for r in selected],
        'promoted': [],
        'publish_attempts': [],
        'before_counts': before,
    }

    if not args.dry_run:
        rescue = load_rescue_module()
        for row in selected:
            path = row['path']
            changed_offer = fix_offer_if_needed(path, row['desired_offer'], dry_run=False)
            ok, msg = rescue.repair(path)
            report['promoted'].append({'file': row['file'], 'site': row['site'], 'ok': ok, 'msg': msg, 'offer_fixed': changed_offer, 'desired_offer': row['desired_offer']})

        # Publish bounded, one pass at a time, prioritizing unpre/untab/skewese money paths.
        attempts = 0
        for site in ['unpre', 'untab', 'skewese']:
            while attempts < args.publish_wp_limit and list(REVIEWED.glob(f'*_wp-{site}_*.md')):
                pub = run_publish(site)
                report['publish_attempts'].append(pub)
                attempts += 1
                if not pub['success']:
                    break

    report['after_counts'] = count_state()
    report['finished_at'] = datetime.now().isoformat(timespec='seconds')
    DATA.mkdir(parents=True, exist_ok=True)
    out_path = DATA / 'revenue_priority_ops_latest.json'
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    ok_pubs = [p for p in report['publish_attempts'] if p.get('success')]
    if args.dry_run:
        print(f"수익 우선 운영 dry-run: 후보 {len(selected)}개 선별, 발행 없음. report={out_path}")
    else:
        print(f"수익 우선 운영 완료: promoted {sum(1 for p in report['promoted'] if p.get('ok'))}/{len(report['promoted'])}, published {len(ok_pubs)}/{len(report['publish_attempts'])}. report={out_path}")
        for pub in ok_pubs:
            print(f"- {pub['site']}: {pub['url']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
